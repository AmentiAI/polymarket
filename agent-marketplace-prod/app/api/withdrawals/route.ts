import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { createPayout } from '@/lib/paypal'

// GET /api/withdrawals - List user's withdrawals
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const userId = searchParams.get('userId')

    if (!userId) {
      return NextResponse.json(
        { error: 'Missing userId parameter' },
        { status: 400 }
      )
    }

    const withdrawals = await prisma.withdrawal.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      take: 50
    })

    return NextResponse.json(withdrawals)
  } catch (error) {
    console.error('Error fetching withdrawals:', error)
    return NextResponse.json(
      { error: 'Failed to fetch withdrawals' },
      { status: 500 }
    )
  }
}

// POST /api/withdrawals - Request a withdrawal
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { userId, amountUSD, paypalEmail } = body

    // Validation
    if (!userId || !amountUSD || !paypalEmail) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    if (amountUSD < 10) {
      return NextResponse.json(
        { error: 'Minimum withdrawal amount is $10' },
        { status: 400 }
      )
    }

    // Get user's available balance
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { availableBalance: true }
    })

    if (!user) {
      return NextResponse.json(
        { error: 'User not found' },
        { status: 404 }
      )
    }

    if (user.availableBalance < amountUSD) {
      return NextResponse.json(
        { error: 'Insufficient balance' },
        { status: 400 }
      )
    }

    // Create payout via PayPal
    let payoutBatchId = ''
    let payoutItemId = ''
    
    try {
      const payout = await createPayout(paypalEmail, amountUSD, `Withdrawal for user ${userId}`)
      payoutBatchId = payout.batch_header.payout_batch_id
      payoutItemId = payout.items[0].payout_item_id
    } catch (paypalError: any) {
      console.error('PayPal payout error:', paypalError)
      return NextResponse.json(
        { error: 'Failed to process payout. Please check your PayPal email and try again.' },
        { status: 500 }
      )
    }

    // Create withdrawal record
    const withdrawal = await prisma.withdrawal.create({
      data: {
        userId,
        amountUSD,
        paypalEmail,
        status: 'PENDING',
        payoutBatchId,
        payoutItemId
      }
    })

    // Deduct from available balance
    await prisma.user.update({
      where: { id: userId },
      data: {
        availableBalance: {
          decrement: amountUSD
        }
      }
    })

    return NextResponse.json(withdrawal, { status: 201 })
  } catch (error) {
    console.error('Error creating withdrawal:', error)
    return NextResponse.json(
      { error: 'Failed to create withdrawal' },
      { status: 500 }
    )
  }
}
