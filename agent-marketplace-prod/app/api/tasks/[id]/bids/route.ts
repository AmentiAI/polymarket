import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// POST /api/tasks/[id]/bids - Submit a bid
export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json()
    const { agentId, message, deliveryTime } = body

    // Validation
    if (!agentId || !message) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    // Check if task exists and is open
    const task = await prisma.task.findUnique({
      where: { id: params.id }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    if (task.status !== 'OPEN') {
      return NextResponse.json(
        { error: 'Task is not open for bids' },
        { status: 400 }
      )
    }

    // Check if agent already bid
    const existingBid = await prisma.bid.findFirst({
      where: {
        taskId: params.id,
        agentId
      }
    })

    if (existingBid) {
      return NextResponse.json(
        { error: 'You have already submitted a bid for this task' },
        { status: 400 }
      )
    }

    const bid = await prisma.bid.create({
      data: {
        taskId: params.id,
        agentId,
        message,
        deliveryTime,
        status: 'PENDING'
      },
      include: {
        agent: {
          select: {
            id: true,
            name: true,
            image: true,
            rating: true,
            totalEarnings: true
          }
        },
        task: {
          select: {
            id: true,
            title: true,
            priceUSD: true
          }
        }
      }
    })

    return NextResponse.json(bid, { status: 201 })
  } catch (error) {
    console.error('Error creating bid:', error)
    return NextResponse.json(
      { error: 'Failed to create bid' },
      { status: 500 }
    )
  }
}
