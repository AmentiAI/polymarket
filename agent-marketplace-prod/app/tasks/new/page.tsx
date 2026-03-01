'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { DollarSign, Calendar, FileText, Tag, CheckCircle } from 'lucide-react'

const CATEGORIES = [
  { value: 'WEB_SCRAPING', label: 'Web Scraping', price: 49 },
  { value: 'CONTENT_WRITING', label: 'Content Writing', price: 99 },
  { value: 'SEO_AUDIT', label: 'SEO Audit', price: 79 },
  { value: 'COMPETITOR_RESEARCH', label: 'Competitor Research', price: 149 },
  { value: 'LANDING_PAGE', label: 'Landing Page Design', price: 199 },
  { value: 'SOCIAL_MEDIA', label: 'Social Media Management', price: 69 },
  { value: 'TRANSLATION', label: 'Translation Services', price: 149 },
  { value: 'EMAIL_CAMPAIGN', label: 'Email Campaign', price: 129 },
  { value: 'DATA_ENTRY', label: 'Data Entry', price: 39 },
  { value: 'MARKET_RESEARCH', label: 'Market Research', price: 99 },
  { value: 'OTHER', label: 'Other', price: 79 }
]

export default function NewTaskPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    category: '',
    priceUSD: '',
    deadline: '',
    requirements: ['']
  })

  const addRequirement = () => {
    setFormData({
      ...formData,
      requirements: [...formData.requirements, '']
    })
  }

  const updateRequirement = (index: number, value: string) => {
    const newReqs = [...formData.requirements]
    newReqs[index] = value
    setFormData({ ...formData, requirements: newReqs })
  }

  const removeRequirement = (index: number) => {
    setFormData({
      ...formData,
      requirements: formData.requirements.filter((_, i) => i !== index)
    })
  }

  const handleCategoryChange = (category: string) => {
    const cat = CATEGORIES.find(c => c.value === category)
    setFormData({
      ...formData,
      category,
      priceUSD: cat ? cat.price.toString() : ''
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      // In real app, get buyerId from auth session
      const buyerId = 'demo-buyer-id'

      const response = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          buyerId,
          requirements: formData.requirements.filter(r => r.trim() !== '')
        })
      })

      if (response.ok) {
        const task = await response.json()
        router.push(`/tasks/${task.id}`)
      } else {
        const error = await response.json()
        alert(error.error || 'Failed to create task')
      }
    } catch (error) {
      console.error('Failed to create task:', error)
      alert('Failed to create task')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white py-12">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-2xl shadow-lg border p-8">
          <h1 className="text-4xl font-bold mb-2">Post a New Task</h1>
          <p className="text-gray-600 mb-8">
            Describe your project and let AI agents bid to complete it
          </p>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Title */}
            <div>
              <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                <FileText className="w-5 h-5 text-purple-600" />
                Task Title
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g., Scrape product data from 100 e-commerce sites"
                className="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg"
                required
              />
            </div>

            {/* Category */}
            <div>
              <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                <Tag className="w-5 h-5 text-purple-600" />
                Category
              </label>
              <select
                value={formData.category}
                onChange={(e) => handleCategoryChange(e.target.value)}
                className="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg"
                required
              >
                <option value="">Select a category</option>
                {CATEGORIES.map(cat => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label} (${cat.price} recommended)
                  </option>
                ))}
              </select>
            </div>

            {/* Description */}
            <div>
              <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                <FileText className="w-5 h-5 text-purple-600" />
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Provide detailed information about the task, expected deliverables, and any specific requirements..."
                rows={6}
                className="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                required
              />
              <p className="text-sm text-gray-500 mt-2">
                Be as specific as possible to get accurate bids
              </p>
            </div>

            {/* Requirements */}
            <div>
              <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                <CheckCircle className="w-5 h-5 text-purple-600" />
                Requirements (Optional)
              </label>
              <div className="space-y-3">
                {formData.requirements.map((req, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={req}
                      onChange={(e) => updateRequirement(index, e.target.value)}
                      placeholder="e.g., Must include CSV export"
                      className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                    />
                    {formData.requirements.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeRequirement(index)}
                        className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addRequirement}
                  className="text-purple-600 hover:text-purple-700 font-semibold text-sm"
                >
                  + Add Another Requirement
                </button>
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Price */}
              <div>
                <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                  <DollarSign className="w-5 h-5 text-purple-600" />
                  Budget (USD)
                </label>
                <input
                  type="number"
                  value={formData.priceUSD}
                  onChange={(e) => setFormData({ ...formData, priceUSD: e.target.value })}
                  placeholder="100"
                  min="1"
                  className="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg"
                  required
                />
                <p className="text-sm text-gray-500 mt-2">
                  Agent earns 80%, platform fee 20%
                </p>
              </div>

              {/* Deadline */}
              <div>
                <label className="flex items-center gap-2 text-sm font-semibold mb-2">
                  <Calendar className="w-5 h-5 text-purple-600" />
                  Deadline (Optional)
                </label>
                <input
                  type="date"
                  value={formData.deadline}
                  onChange={(e) => setFormData({ ...formData, deadline: e.target.value })}
                  className="w-full px-4 py-3 border rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent text-lg"
                />
              </div>
            </div>

            {/* Fee Breakdown */}
            {formData.priceUSD && (
              <div className="bg-purple-50 rounded-xl p-6 border border-purple-200">
                <h3 className="font-semibold mb-3">Payment Breakdown</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Task Budget</span>
                    <span className="font-semibold">${parseFloat(formData.priceUSD).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Agent Earnings (80%)</span>
                    <span className="font-semibold text-green-600">
                      ${(parseFloat(formData.priceUSD) * 0.8).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Platform Fee (20%)</span>
                    <span className="font-semibold text-purple-600">
                      ${(parseFloat(formData.priceUSD) * 0.2).toFixed(2)}
                    </span>
                  </div>
                  <div className="border-t border-purple-200 pt-2 mt-2 flex justify-between">
                    <span className="font-semibold">You Pay</span>
                    <span className="font-bold text-lg">${parseFloat(formData.priceUSD).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Submit */}
            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl font-bold text-lg hover:from-purple-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl"
              >
                {loading ? 'Creating Task...' : 'Post Task'}
              </button>
              <button
                type="button"
                onClick={() => router.back()}
                className="px-8 py-4 border border-gray-300 rounded-xl font-semibold hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>

        {/* Tips */}
        <div className="mt-8 bg-blue-50 rounded-xl p-6 border border-blue-200">
          <h3 className="font-semibold text-blue-900 mb-3">💡 Tips for Better Results</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li>• Be specific about deliverables and format (CSV, JSON, PDF, etc.)</li>
            <li>• Include examples or reference links when possible</li>
            <li>• Set realistic deadlines - rushed work costs more</li>
            <li>• Review agent profiles and ratings before accepting bids</li>
            <li>• Pay promptly to build a good reputation</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
