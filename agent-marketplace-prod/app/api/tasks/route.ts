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
      where.priceUSD = {}
      if (minPrice) where.priceUSD.gte = parseFloat(minPrice)
      if (maxPrice) where.priceUSD.lte = parseFloat(maxPrice)
    }

    const tasks = await prisma.task.findMany({
      where,
      include: {
        buyer: {
          select: {
            id: true,
            name: true,
            image: true,
          }
        },
        _count: {
          select: {
            bids: true
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
      priceUSD,
      deadline,
      requirements,
      buyerId
    } = body

    // Validation
    if (!title || !description || !category || !priceUSD || !buyerId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      )
    }

    if (priceUSD < 1) {
      return NextResponse.json(
        { error: 'Price must be at least $1' },
        { status: 400 }
      )
    }

    const task = await prisma.task.create({
      data: {
        title,
        description,
        category,
        priceUSD: parseFloat(priceUSD),
        deadline: deadline ? new Date(deadline) : null,
        requirements: requirements || [],
        buyerId,
        status: 'OPEN'
      },
      include: {
        buyer: {
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
