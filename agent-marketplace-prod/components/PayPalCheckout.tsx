'use client'

import { useState } from 'react'
import { PayPalScriptProvider, PayPalButtons } from '@paypal/react-paypal-js'

interface PayPalCheckoutProps {
  taskId: string
  amount: number
  onSuccess: () => void
  onError: (error: string) => void
}

export default function PayPalCheckout({ taskId, amount, onSuccess, onError }: PayPalCheckoutProps) {
  const [loading, setLoading] = useState(false)

  const createOrder = async () => {
    try {
      setLoading(true)
      // Get buyerId from auth session (placeholder for now)
      const buyerId = 'demo-buyer-id'

      const response = await fetch('/api/payments/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ taskId, buyerId })
      })

      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to create order')
      }

      return data.orderId
    } catch (error: any) {
      onError(error.message)
      throw error
    } finally {
      setLoading(false)
    }
  }

  const captureOrder = async (orderId: string) => {
    try {
      setLoading(true)
      const response = await fetch('/api/payments/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderId, taskId })
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Failed to capture payment')
      }

      onSuccess()
      return data
    } catch (error: any) {
      onError(error.message)
      throw error
    } finally {
      setLoading(false)
    }
  }

  const clientId = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID || 'test'

  return (
    <div className="w-full">
      {loading && (
        <div className="absolute inset-0 bg-white/80 flex items-center justify-center rounded-xl z-10">
          <div className="text-center">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-purple-600 border-t-transparent"></div>
            <p className="mt-2 text-sm text-gray-600">Processing payment...</p>
          </div>
        </div>
      )}
      
      <PayPalScriptProvider
        options={{
          clientId,
          currency: 'USD',
          intent: 'capture'
        }}
      >
        <PayPalButtons
          style={{
            layout: 'vertical',
            color: 'gold',
            shape: 'rect',
            label: 'pay'
          }}
          createOrder={createOrder}
          onApprove={async (data) => {
            await captureOrder(data.orderID)
          }}
          onError={(err) => {
            console.error('PayPal error:', err)
            onError('Payment failed. Please try again.')
          }}
        />
      </PayPalScriptProvider>

      <div className="mt-4 text-center text-sm text-gray-600">
        <p>💳 Secure payment powered by PayPal</p>
        <p className="mt-1">Funds held in escrow until work is approved</p>
      </div>
    </div>
  )
}
