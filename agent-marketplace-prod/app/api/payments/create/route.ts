import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { createOrder } from '@/lib/paypal'

// POST /api/payments/create - Create PayPal order
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { taskId, buyerId } = body

    if (!taskId || !buyerId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // Get task details
    const task = await prisma.task.findUnique({
      where: { id: taskId },
      include: {
        buyer: true,
        winner: true
      }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    // Verify buyer
    if (task.buyerId !== buyerId) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 403 }
      )
    }

    // Check if payment already exists
    const existingPayment = await prisma.payment.findUnique({
      where: { taskId }
    })

    if (existingPayment) {
      return NextResponse.json(
        { error: 'Payment already created for this task' },
        { status: 400 }
      )
    }

    // Create PayPal order
    const order = await createOrder(task.priceUSD)

    // Create payment record
    const payment = await prisma.payment.create({
      data: {
        taskId,
        buyerId,
        agentId: task.winnerId || '',
        amountUSD: task.priceUSD,
        platformFeeUSD: task.priceUSD * 0.2, // 20% fee
        agentEarningsUSD: task.priceUSD * 0.8, // 80% to agent
        paypalOrderId: order.id,
        status: 'PENDING'
      }
    })

    return NextResponse.json({
      payment,
      orderId: order.id
    })
  } catch (error) {
    console.error('Error creating payment:', error)
    return NextResponse.json(
      { error: 'Failed to create payment' },
      { status: 500 }
    )
  }
}
