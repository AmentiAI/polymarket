import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

// GET /api/tasks - List all tasks with filters
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const category = searchParams.get('category')
    const status = searchParams.get('status')
    const minPrice = searchParams.get('minPrice')
    const maxPrice = searchParams.get('maxPrice')

    const where: any = {}
    
    if (category) {
      where.category = category
    }
    
    if (status) {
      where.status = status
    }
    
    if (minPrice || maxPrice) {
      where.budget = {}
      if (minPrice) where.budget.gte = parseFloat(minPrice)
      if (maxPrice) where.budget.lte = parseFloat(maxPrice)
    }

    const tasks = await prisma.task.findMany({
      where,
      include: {
        poster: {
          select: {
            id: true,
            name: true,
            image: true,
          }
        }
      },
      orderBy: {
        createdAt: 'desc'
      },
      take: 50
    })

    return NextResponse.json(tasks)
  } catch (error) {
    console.error('Error fetching tasks:', error)
    return NextResponse.json(
      { error: 'Failed to fetch tasks' },
      { status: 500 }
    )
  }
}

// POST /api/tasks - Create a new task
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const {
      title,
      description,
      category,
      budget,
      deadline,
      posterId
    } = body

    // Validation
    if (!title || !description || !category || !budget || !posterId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    if (budget < 1) {
      return NextResponse.json(
        { error: 'Budget must be at least $1' },
        { status: 400 }
      )
    }

    const task = await prisma.task.create({
      data: {
        title,
        description,
        category,
        budget: parseFloat(budget),
        deadline: deadline ? new Date(deadline) : null,
        posterId,
        status: 'OPEN'
      },
      include: {
        poster: {
          select: {
            id: true,
            name: true,
            email: true,
            image: true
          }
        }
      }
    })

    return NextResponse.json(task, { status: 201 })
  } catch (error) {
    console.error('Error creating task:', error)
    return NextResponse.json(
      { error: 'Failed to create task' },
      { status: 500 }
    )
  }
}
