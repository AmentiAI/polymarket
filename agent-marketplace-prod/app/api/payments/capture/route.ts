import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { captureOrder } from '@/lib/paypal'

// POST /api/payments/capture - Capture PayPal payment
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { orderId, taskId } = body

    if (!orderId || !taskId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // Get payment record
    const payment = await prisma.payment.findFirst({
      where: {
        paypalOrderId: orderId,
        taskId
      },
      include: {
        task: {
          include: {
            agent: true
          }
        }
      }
    })

    if (!payment) {
      return NextResponse.json(
        { error: 'Payment not found' },
        { status: 404 }
      )
    }

    if (payment.status === 'CAPTURED' || payment.status === 'RELEASED') {
      return NextResponse.json(
        { error: 'Payment already captured' },
        { status: 400 }
      )
    }

    // Capture the order
    const captureData = await captureOrder(orderId)

    // Update payment record
    const updatedPayment = await prisma.payment.update({
      where: { id: payment.id },
      data: {
        status: 'CAPTURED',
        paypalCaptureId: captureData.id,
        heldAt: new Date()
      }
    })

    // Update task status to IN_PROGRESS
    await prisma.task.update({
      where: { id: taskId },
      data: {
        status: 'IN_PROGRESS'
      }
    })

    // Update agent earnings
    if (payment.task.agent) {
      await prisma.user.update({
        where: { id: payment.task.agentId! },
        data: {
          totalEarned: {
            increment: payment.agentPayout
          }
        }
      })
    }

    return NextResponse.json({
      success: true,
      payment: updatedPayment,
      captureId: captureData.id
    })
  } catch (error) {
    console.error('Error capturing payment:', error)
    return NextResponse.json(
      { error: 'Failed to capture payment' },
      { status: 500 }
    )
  }
}
