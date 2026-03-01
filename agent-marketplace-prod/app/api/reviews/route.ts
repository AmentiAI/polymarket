import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// POST /api/reviews - Create a review
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { taskId, reviewerId, revieweeId, rating, comment } = body

    // Validation
    if (!taskId || !reviewerId || !revieweeId || !rating) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    if (rating < 1 || rating > 5) {
      return NextResponse.json(
        { error: 'Rating must be between 1 and 5' },
        { status: 400 }
      )
    }

    // Check if task exists and is completed
    const task = await prisma.task.findUnique({
      where: { id: taskId }
    })

    if (!task) {
      return NextResponse.json(
        { error: 'Task not found' },
        { status: 404 }
      )
    }

    if (task.status !== 'COMPLETED') {
      return NextResponse.json(
        { error: 'Can only review completed tasks' },
        { status: 400 }
      )
    }

    // Check if review already exists
    const existingReview = await prisma.review.findUnique({
      where: { taskId }
    })

    if (existingReview) {
      return NextResponse.json(
        { error: 'Review already exists for this task' },
        { status: 400 }
      )
    }

    // Create review
    const review = await prisma.review.create({
      data: {
        taskId,
        reviewerId,
        revieweeId,
        rating,
        comment: comment || ''
      }
    })

    // Update reviewee's rating
    const reviews = await prisma.review.findMany({
      where: { revieweeId },
      select: { rating: true }
    })

    const avgRating = reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length

    await prisma.user.update({
      where: { id: revieweeId },
      data: { rating: avgRating }
    })

    return NextResponse.json(review, { status: 201 })
  } catch (error) {
    console.error('Error creating review:', error)
    return NextResponse.json(
      { error: 'Failed to create review' },
      { status: 500 }
    )
  }
}
