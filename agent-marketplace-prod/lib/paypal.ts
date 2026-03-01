// PayPal Integration for AgentMarketplace
// Handles payments, escrow, and payouts

const PAYPAL_CLIENT_ID = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID!
const PAYPAL_CLIENT_SECRET = process.env.PAYPAL_CLIENT_SECRET!
const PAYPAL_MODE = process.env.PAYPAL_MODE || 'sandbox' // sandbox or live

const PAYPAL_API_URL =
  PAYPAL_MODE === 'live'
    ? 'https://api-m.paypal.com'
    : 'https://api-m.sandbox.paypal.com'

// ─────────────────────────────────────────────
// AUTHENTICATION
// ─────────────────────────────────────────────

async function getAccessToken(): Promise<string> {
  const auth = Buffer.from(
    `${PAYPAL_CLIENT_ID}:${PAYPAL_CLIENT_SECRET}`
  ).toString('base64')

  const response = await fetch(`${PAYPAL_API_URL}/v1/oauth2/token`, {
    method: 'POST',
    headers: {
      Authorization: `Basic ${auth}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
  })

  if (!response.ok) {
    throw new Error('Failed to get PayPal access token')
  }

  const data = await response.json()
  return data.access_token
}

// ─────────────────────────────────────────────
// ORDERS (Buyer Payment)
// ─────────────────────────────────────────────

export async function createOrder(amount: number, currency: string = 'USD') {
  const accessToken = await getAccessToken()

  const order = {
    intent: 'CAPTURE',
    purchase_units: [
      {
        amount: {
          currency_code: currency,
          value: amount.toFixed(2),
        },
      },
    ],
  }

  const response = await fetch(`${PAYPAL_API_URL}/v2/checkout/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(order),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to create PayPal order: ${error}`)
  }

  return await response.json()
}

// ─────────────────────────────────────────────
// CAPTURE (Complete Payment)
// ─────────────────────────────────────────────

export async function captureOrder(orderId: string) {
  const accessToken = await getAccessToken()

  const response = await fetch(
    `${PAYPAL_API_URL}/v2/checkout/orders/${orderId}/capture`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
    }
  )

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to capture PayPal order: ${error}`)
  }

  const data = await response.json()
  return data.purchase_units[0].payments.captures[0]
}

// ─────────────────────────────────────────────
// PAYOUTS (Pay Agents)
// ─────────────────────────────────────────────

export async function createPayout(
  paypalEmail: string,
  amount: number,
  note: string,
  currency: string = 'USD'
) {
  const accessToken = await getAccessToken()

  const payout = {
    sender_batch_header: {
      sender_batch_id: `payout_${Date.now()}`,
      email_subject: "You've received payment from AgentMarketplace!",
      email_message: note,
    },
    items: [
      {
        recipient_type: 'EMAIL',
        amount: {
          value: amount.toFixed(2),
          currency: currency,
        },
        note: note,
        receiver: paypalEmail,
      },
    ],
  }

  const response = await fetch(`${PAYPAL_API_URL}/v1/payments/payouts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payout),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to create payout: ${error}`)
  }

  return await response.json()
}

// ─────────────────────────────────────────────
// REFUNDS (Dispute Resolution)
// ─────────────────────────────────────────────

export async function refundCapture(
  captureId: string,
  amount?: number,
  currency: string = 'USD'
) {
  const accessToken = await getAccessToken()

  const refundData: any = {}
  if (amount) {
    refundData.amount = {
      value: amount.toFixed(2),
      currency_code: currency,
    }
  }

  const response = await fetch(
    `${PAYPAL_API_URL}/v2/payments/captures/${captureId}/refund`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(refundData),
    }
  )

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to refund: ${error}`)
  }

  return await response.json()
}

// ─────────────────────────────────────────────
// WEBHOOK VERIFICATION
// ─────────────────────────────────────────────

export async function verifyWebhook(
  headers: Record<string, string>,
  body: string,
  webhookId: string
): Promise<boolean> {
  const accessToken = await getAccessToken()

  const verificationData = {
    transmission_id: headers['paypal-transmission-id'],
    transmission_time: headers['paypal-transmission-time'],
    cert_url: headers['paypal-cert-url'],
    auth_algo: headers['paypal-auth-algo'],
    transmission_sig: headers['paypal-transmission-sig'],
    webhook_id: webhookId,
    webhook_event: JSON.parse(body),
  }

  const response = await fetch(
    `${PAYPAL_API_URL}/v1/notifications/verify-webhook-signature`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(verificationData),
    }
  )

  if (!response.ok) {
    return false
  }

  const data = await response.json()
  return data.verification_status === 'SUCCESS'
}
