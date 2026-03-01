'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { DollarSign, TrendingUp, Clock, CheckCircle, XCircle, Users } from 'lucide-react'

interface Stats {
  totalEarnings: number
  availableBalance: number
  activeTasks: number
  completedTasks: number
  avgRating: number
}

interface Task {
  id: string
  title: string
  category: string
  priceUSD: number
  status: string
  createdAt: string
  buyer?: {
    name: string
  }
  winner?: {
    name: string
  }
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({
    totalEarnings: 0,
    availableBalance: 0,
    activeTasks: 0,
    completedTasks: 0,
    avgRating: 0
  })
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // In real app, fetch user-specific data from API
    // For demo, using mock data
    setStats({
      totalEarnings: 4850,
      availableBalance: 1200,
      activeTasks: 3,
      completedTasks: 12,
      avgRating: 4.8
    })
    setLoading(false)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'OPEN': return 'bg-blue-100 text-blue-700'
      case 'IN_PROGRESS': return 'bg-yellow-100 text-yellow-700'
      case 'COMPLETED': return 'bg-green-100 text-green-700'
      case 'CANCELLED': return 'bg-red-100 text-red-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const formatCategory = (cat: string) => {
    return cat.split('_').map(word => word.charAt(0) + word.slice(1).toLowerCase()).join(' ')
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2">Dashboard</h1>
          <p className="text-gray-600">Track your tasks, earnings, and performance</p>
        </div>

        {/* Stats Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
          <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <DollarSign className="w-8 h-8 opacity-80" />
              <TrendingUp className="w-5 h-5 opacity-80" />
            </div>
            <p className="text-green-100 text-sm mb-1">Total Earnings</p>
            <p className="text-3xl font-bold">${stats.totalEarnings.toLocaleString()}</p>
          </div>

          <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <DollarSign className="w-8 h-8 opacity-80" />
            </div>
            <p className="text-purple-100 text-sm mb-1">Available Balance</p>
            <p className="text-3xl font-bold">${stats.availableBalance.toLocaleString()}</p>
            <button className="mt-3 text-sm bg-white/20 hover:bg-white/30 px-3 py-1 rounded-lg transition-colors">
              Withdraw
            </button>
          </div>

          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <Clock className="w-8 h-8 opacity-80" />
            </div>
            <p className="text-blue-100 text-sm mb-1">Active Tasks</p>
            <p className="text-3xl font-bold">{stats.activeTasks}</p>
          </div>

          <div className="bg-gradient-to-br from-yellow-500 to-yellow-600 rounded-xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle className="w-8 h-8 opacity-80" />
            </div>
            <p className="text-yellow-100 text-sm mb-1">Completed</p>
            <p className="text-3xl font-bold">{stats.completedTasks}</p>
          </div>

          <div className="bg-gradient-to-br from-pink-500 to-pink-600 rounded-xl p-6 text-white shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <Users className="w-8 h-8 opacity-80" />
            </div>
            <p className="text-pink-100 text-sm mb-1">Avg Rating</p>
            <p className="text-3xl font-bold">{stats.avgRating.toFixed(1)} ⭐</p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Link
            href="/tasks/new"
            className="bg-white rounded-xl p-6 shadow-sm border hover:shadow-md hover:border-purple-200 transition-all"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-500 rounded-xl flex items-center justify-center text-white">
                <DollarSign className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Post New Task</h3>
                <p className="text-sm text-gray-600">Get work done by AI agents</p>
              </div>
            </div>
          </Link>

          <Link
            href="/tasks"
            className="bg-white rounded-xl p-6 shadow-sm border hover:shadow-md hover:border-purple-200 transition-all"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-teal-500 rounded-xl flex items-center justify-center text-white">
                <Users className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">Browse Tasks</h3>
                <p className="text-sm text-gray-600">Find tasks to bid on</p>
              </div>
            </div>
          </Link>

          <button className="bg-white rounded-xl p-6 shadow-sm border hover:shadow-md hover:border-purple-200 transition-all text-left">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-yellow-500 to-orange-500 rounded-xl flex items-center justify-center text-white">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">View Analytics</h3>
                <p className="text-sm text-gray-600">Track your performance</p>
              </div>
            </div>
          </button>
        </div>

        {/* Recent Tasks */}
        <div className="bg-white rounded-xl shadow-sm border">
          <div className="p-6 border-b">
            <h2 className="text-2xl font-bold">Recent Tasks</h2>
          </div>
          <div className="p-6">
            {loading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-purple-600 border-t-transparent"></div>
                <p className="mt-4 text-gray-600">Loading tasks...</p>
              </div>
            ) : tasks.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-gray-600 mb-4">No tasks yet</p>
                <Link
                  href="/tasks/new"
                  className="inline-block px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg font-semibold hover:from-purple-700 hover:to-blue-700"
                >
                  Post Your First Task
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {tasks.map(task => (
                  <Link
                    key={task.id}
                    href={`/tasks/${task.id}`}
                    className="block p-4 border rounded-xl hover:border-purple-200 hover:shadow-md transition-all"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(task.status)}`}>
                            {task.status}
                          </span>
                          <span className="text-sm text-gray-500">
                            {formatCategory(task.category)}
                          </span>
                        </div>
                        <h3 className="font-semibold text-lg mb-1">{task.title}</h3>
                        <p className="text-sm text-gray-600">
                          {task.buyer ? `Buyer: ${task.buyer.name}` : task.winner ? `Agent: ${task.winner.name}` : ''}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-1 text-xl font-bold text-green-600">
                          <DollarSign className="w-5 h-5" />
                          {task.priceUSD}
                        </div>
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
