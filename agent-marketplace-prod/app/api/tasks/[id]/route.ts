import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// GET /api/tasks/[id] - Get task details
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const task = await prisma.task.findUnique({
      where: { id },
      include: {
        poster: {
          select: {
            id: true,
            name: true,
            email: true,
            image: true,
            createdAt: true
          }
        },
        agent: {
          select: {
            id: true,
            name: true,
            image: true,
            reputation: true,
            totalEarned: true
          }
        },
        payment: true
      }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    return NextResponse.json(task)
  } catch (error) {
    console.error('Error fetching task:', error)
    return NextResponse.json(
      { error: 'Failed to fetch task' },
      { status: 500 }
    )
  }
}

// PATCH /api/tasks/[id] - Update task status
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()
    const { status, winnerId, buyerId } = body

    const task = await prisma.task.findUnique({
      where: { id }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    // Verify poster owns this task
    if (buyerId && task.posterId !== buyerId) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 403 }
      )
    }

    const updatedTask = await prisma.task.update({
      where: { id },
      data: {
        status,
        agentId: winnerId || task.agentId
      },
      include: {
        poster: {
          select: {
            id: true,
            name: true,
            image: true
          }
        },
        agent: {
          select: {
            id: true,
            name: true,
            image: true
          }
        }
      }
    })

    return NextResponse.json(updatedTask)
  } catch (error) {
    console.error('Error updating task:', error)
    return NextResponse.json(
      { error: 'Failed to update task' },
      { status: 500 }
    )
  }
}

// DELETE /api/tasks/[id] - Delete task (only if no bids)
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const task = await prisma.task.findUnique({
      where: { id }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    if (task.status !== 'OPEN') {
      return NextResponse.json(
        { error: 'Cannot delete task that is not open' },
        { status: 400 }
      )
    }

    await prisma.task.delete({
      where: { id }
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error deleting task:', error)
    return NextResponse.json(
      { error: 'Failed to delete task' },
      { status: 500 }
    )
  }
}
