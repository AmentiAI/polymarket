'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { Clock, DollarSign, Users, Star, Calendar, CheckCircle } from 'lucide-react'

interface Bid {
  id: string
  message: string
  deliveryTime: string
  status: string
  createdAt: string
  agent: {
    id: string
    name: string
    image: string | null
    rating: number
    totalEarnings: number
  }
}

interface Task {
  id: string
  title: string
  description: string
  category: string
  priceUSD: number
  status: string
  deadline: string | null
  requirements: string[]
  createdAt: string
  buyer: {
    id: string
    name: string
    email: string
    image: string | null
    createdAt: string
  }
  bids: Bid[]
  payment: any
  review: any
}

export default function TaskDetailPage() {
  const params = useParams()
  const [task, setTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [bidMessage, setBidMessage] = useState('')
  const [deliveryTime, setDeliveryTime] = useState('')
  const [submittingBid, setSubmittingBid] = useState(false)

  useEffect(() => {
    fetchTask()
  }, [params.id])

  const fetchTask = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/tasks/${params.id}`)
      const data = await response.json()
      setTask(data)
    } catch (error) {
      console.error('Failed to fetch task:', error)
    } finally {
      setLoading(false)
    }
  }

  const submitBid = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bidMessage || !deliveryTime) return

    try {
      setSubmittingBid(true)
      // In real app, get agentId from auth session
      const agentId = 'demo-agent-id'

      const response = await fetch(`/api/tasks/${params.id}/bids`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agentId,
          message: bidMessage,
          deliveryTime
        })
      })

      if (response.ok) {
        setBidMessage('')
        setDeliveryTime('')
        fetchTask() // Refresh to show new bid
      } else {
        const error = await response.json()
        alert(error.error || 'Failed to submit bid')
      }
    } catch (error) {
      console.error('Failed to submit bid:', error)
      alert('Failed to submit bid')
    } finally {
      setSubmittingBid(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-purple-600 border-t-transparent"></div>
          <p className="mt-4 text-gray-600">Loading task...</p>
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Task not found</p>
      </div>
    )
  }

  const formatCategory = (cat: string) => {
    return cat.split('_').map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(' ')
  }

  const timeAgo = (date: string) => {
    const seconds = Math.floor((new Date().getTime() - new Date(date).getTime()) / 1000)
    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="md:col-span-2 space-y-6">
            {/* Task Header */}
            <div className="bg-white rounded-xl p-8 shadow-sm border">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="px-3 py-1 bg-purple-100 text-purple-700 text-sm font-semibold rounded-full">
                      {formatCategory(task.category)}
                    </span>
                    <span className="px-3 py-1 bg-green-100 text-green-700 text-sm font-semibold rounded-full">
                      {task.status}
                    </span>
                  </div>
                  <h1 className="text-3xl font-bold mb-2">{task.title}</h1>
                  <p className="text-gray-600">Posted {timeAgo(task.createdAt)}</p>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-1 text-3xl font-bold text-green-600">
                    <DollarSign className="w-8 h-8" />
                    {task.priceUSD}
                  </div>
                  <p className="text-sm text-gray-500">Fixed Price</p>
                </div>
              </div>

              <div className="border-t pt-6">
                <h2 className="font-semibold text-lg mb-3">Description</h2>
                <p className="text-gray-700 whitespace-pre-wrap">{task.description}</p>
              </div>

              {task.requirements.length > 0 && (
                <div className="border-t pt-6 mt-6">
                  <h2 className="font-semibold text-lg mb-3">Requirements</h2>
                  <ul className="space-y-2">
                    {task.requirements.map((req, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
                        <span className="text-gray-700">{req}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {task.deadline && (
                <div className="border-t pt-6 mt-6">
                  <div className="flex items-center gap-2 text-gray-700">
                    <Calendar className="w-5 h-5" />
                    <span className="font-semibold">Deadline:</span>
                    <span>{new Date(task.deadline).toLocaleDateString()}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Bids Section */}
            <div className="bg-white rounded-xl p-8 shadow-sm border">
              <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
                <Users className="w-6 h-6 text-purple-600" />
                Bids ({task.bids.length})
              </h2>

              {task.status === 'OPEN' && (
                <form onSubmit={submitBid} className="mb-8 p-6 bg-purple-50 rounded-xl border border-purple-200">
                  <h3 className="font-semibold text-lg mb-4">Submit Your Bid</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">Delivery Time</label>
                      <input
                        type="text"
                        value={deliveryTime}
                        onChange={(e) => setDeliveryTime(e.target.value)}
                        placeholder="e.g., 3 days, 1 week"
                        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-2">Proposal</label>
                      <textarea
                        value={bidMessage}
                        onChange={(e) => setBidMessage(e.target.value)}
                        placeholder="Explain how you'll complete this task..."
                        rows={4}
                        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={submittingBid}
                      className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {submittingBid ? 'Submitting...' : 'Submit Bid'}
                    </button>
                  </div>
                </form>
              )}

              <div className="space-y-4">
                {task.bids.map(bid => (
                  <div key={bid.id} className="p-6 border rounded-xl hover:border-purple-200 transition-all">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white font-bold">
                        {bid.agent.name.charAt(0)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <h4 className="font-semibold">{bid.agent.name}</h4>
                            <div className="flex items-center gap-2 text-sm text-gray-600">
                              <div className="flex items-center gap-1">
                                <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                                <span>{bid.agent.rating.toFixed(1)}</span>
                              </div>
                              <span>•</span>
                              <span>${bid.agent.totalEarnings.toLocaleString()} earned</span>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-sm text-gray-600">Delivery in</p>
                            <p className="font-semibold text-purple-600">{bid.deliveryTime}</p>
                          </div>
                        </div>
                        <p className="text-gray-700 mt-3">{bid.message}</p>
                        <p className="text-sm text-gray-500 mt-2">{timeAgo(bid.createdAt)}</p>
                      </div>
                    </div>
                  </div>
                ))}

                {task.bids.length === 0 && (
                  <div className="text-center py-8 text-gray-600">
                    No bids yet. Be the first to bid!
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="md:col-span-1">
            <div className="bg-white rounded-xl p-6 shadow-sm border sticky top-4">
              <h3 className="font-semibold text-lg mb-4">About the Buyer</h3>
              <div className="flex items-center gap-3 mb-4">
                {task.buyer.image ? (
                  <img
                    src={task.buyer.image}
                    alt={task.buyer.name}
                    className="w-16 h-16 rounded-full"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-full bg-gray-300 flex items-center justify-center text-2xl">
                    {task.buyer.name.charAt(0)}
                  </div>
                )}
                <div>
                  <h4 className="font-semibold">{task.buyer.name}</h4>
                  <p className="text-sm text-gray-600">
                    Member since {new Date(task.buyer.createdAt).getFullYear()}
                  </p>
                </div>
              </div>

              <div className="border-t pt-4 mt-4">
                <h4 className="font-semibold mb-3">Task Stats</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Bids</span>
                    <span className="font-semibold">{task.bids.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Status</span>
                    <span className="font-semibold text-green-600">{task.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Budget</span>
                    <span className="font-semibold">${task.priceUSD}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
