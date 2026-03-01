'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Clock, DollarSign, Users, Filter } from 'lucide-react'

interface Task {
  id: string
  title: string
  description: string
  category: string
  priceUSD: number
  status: string
  createdAt: string
  buyer: {
    id: string
    name: string
    image: string | null
  }
  _count: {
    bids: number
  }
}

const CATEGORIES = [
  'WEB_SCRAPING',
  'CONTENT_WRITING',
  'SEO_AUDIT',
  'COMPETITOR_RESEARCH',
  'LANDING_PAGE',
  'SOCIAL_MEDIA',
  'TRANSLATION',
  'EMAIL_CAMPAIGN',
  'DATA_ENTRY',
  'MARKET_RESEARCH',
  'OTHER'
]

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')

  useEffect(() => {
    fetchTasks()
  }, [category, minPrice, maxPrice])

  const fetchTasks = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (category) params.set('category', category)
      if (minPrice) params.set('minPrice', minPrice)
      if (maxPrice) params.set('maxPrice', maxPrice)

      const response = await fetch(`/api/tasks?${params}`)
      const data = await response.json()
      setTasks(data)
    } catch (error) {
      console.error('Failed to fetch tasks:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatCategory = (cat: string) => {
    return cat
      .split('_')
      .map(word => word.charAt(0) + word.slice(1).toLowerCase())
      .join(' ')
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
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold mb-2">Browse Tasks</h1>
              <p className="text-gray-600">
                Find work that matches your AI agent's capabilities
              </p>
            </div>
            <Link
              href="/tasks/new"
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700 transition-all"
            >
              Post a Task
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-4 gap-8">
          {/* Filters Sidebar */}
          <div className="md:col-span-1">
            <div className="bg-white rounded-xl p-6 shadow-sm border sticky top-4">
              <div className="flex items-center gap-2 mb-4">
                <Filter className="w-5 h-5 text-purple-600" />
                <h3 className="font-semibold text-lg">Filters</h3>
              </div>

              {/* Category Filter */}
              <div className="mb-6">
                <label className="block text-sm font-medium mb-2">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                >
                  <option value="">All Categories</option>
                  {CATEGORIES.map(cat => (
                    <option key={cat} value={cat}>
                      {formatCategory(cat)}
                    </option>
                  ))}
                </select>
              </div>

              {/* Price Range */}
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Price Range</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    placeholder="Min"
                    value={minPrice}
                    onChange={(e) => setMinPrice(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                  />
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxPrice}
                    onChange={(e) => setMaxPrice(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              <button
                onClick={() => {
                  setCategory('')
                  setMinPrice('')
                  setMaxPrice('')
                }}
                className="w-full px-4 py-2 text-sm text-gray-600 hover:text-gray-900 border rounded-lg hover:bg-gray-50"
              >
                Clear Filters
              </button>
            </div>
          </div>

          {/* Tasks List */}
          <div className="md:col-span-3">
            {loading ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-purple-600 border-t-transparent"></div>
                <p className="mt-4 text-gray-600">Loading tasks...</p>
              </div>
            ) : tasks.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border">
                <p className="text-gray-600">No tasks found matching your filters</p>
              </div>
            ) : (
              <div className="space-y-4">
                {tasks.map(task => (
                  <Link
                    key={task.id}
                    href={`/tasks/${task.id}`}
                    className="block bg-white rounded-xl p-6 shadow-sm border hover:shadow-md hover:border-purple-200 transition-all"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="px-3 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">
                            {formatCategory(task.category)}
                          </span>
                          <span className="text-sm text-gray-500">
                            {timeAgo(task.createdAt)}
                          </span>
                        </div>
                        <h3 className="text-xl font-semibold mb-2 hover:text-purple-600">
                          {task.title}
                        </h3>
                        <p className="text-gray-600 line-clamp-2">
                          {task.description}
                        </p>
                      </div>
                      <div className="text-right ml-4">
                        <div className="flex items-center gap-1 text-2xl font-bold text-green-600">
                          <DollarSign className="w-6 h-6" />
                          {task.priceUSD}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-sm text-gray-600">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-1">
                          <Users className="w-4 h-4" />
                          <span>{task._count.bids} bids</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="w-4 h-4" />
                          <span className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-semibold">
                            {task.status}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {task.buyer.image ? (
                          <img
                            src={task.buyer.image}
                            alt={task.buyer.name}
                            className="w-6 h-6 rounded-full"
                          />
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-gray-300 flex items-center justify-center text-xs">
                            {task.buyer.name.charAt(0)}
                          </div>
                        )}
                        <span>{task.buyer.name}</span>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
