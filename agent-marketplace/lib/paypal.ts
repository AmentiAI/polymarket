// PayPal Integration for AgentMarketplace
// Handles payments, escrow, and payouts

const PAYPAL_CLIENT_ID = process.env.NEXT_PUBLIC_PAYPAL_CLIENT_ID!;
const PAYPAL_CLIENT_SECRET = process.env.PAYPAL_CLIENT_SECRET!;
const PAYPAL_MODE = process.env.PAYPAL_MODE || "sandbox"; // sandbox or live

const PAYPAL_API_URL =
  PAYPAL_MODE === "live"
    ? "https://api-m.paypal.com"
    : "https://api-m.sandbox.paypal.com";

// ─────────────────────────────────────────────
// AUTHENTICATION
// ─────────────────────────────────────────────

async function getAccessToken(): Promise<string> {
  const auth = Buffer.from(
    `${PAYPAL_CLIENT_ID}:${PAYPAL_CLIENT_SECRET}`
  ).toString("base64");

  const response = await fetch(`${PAYPAL_API_URL}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });

  if (!response.ok) {
    throw new Error("Failed to get PayPal access token");
  }

  const data = await response.json();
  return data.access_token;
}

// ─────────────────────────────────────────────
// ORDERS (Buyer Payment)
// ─────────────────────────────────────────────

export async function createPayPalOrder(
  taskId: string,
  amount: number,
  currency: string = "USD"
) {
  const accessToken = await getAccessToken();

  const platformFee = amount * 0.2; // 20% commission
  const agentPayout = amount * 0.8; // 80% to agent

  const order = {
    intent: "CAPTURE",
    purchase_units: [
      {
        reference_id: taskId,
        description: `AgentMarketplace Task #${taskId.slice(0, 8)}`,
        amount: {
          currency_code: currency,
          value: amount.toFixed(2),
        },
      },
    ],
    application_context: {
      return_url: `${process.env.NEXT_PUBLIC_URL}/tasks/${taskId}?payment=success`,
      cancel_url: `${process.env.NEXT_PUBLIC_URL}/tasks/${taskId}?payment=cancelled`,
      shipping_preference: "NO_SHIPPING",
      user_action: "PAY_NOW",
      brand_name: "AgentMarketplace",
    },
  };

  const response = await fetch(`${PAYPAL_API_URL}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(order),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create PayPal order: ${error}`);
  }

  const data = await response.json();
  return {
    orderId: data.id,
    approvalUrl: data.links.find((link: any) => link.rel === "approve")?.href,
  };
}

// ─────────────────────────────────────────────
// CAPTURE (Complete Payment)
// ─────────────────────────────────────────────

export async function capturePayPalOrder(orderId: string) {
  const accessToken = await getAccessToken();

  const response = await fetch(
    `${PAYPAL_API_URL}/v2/checkout/orders/${orderId}/capture`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to capture PayPal order: ${error}`);
  }

  const data = await response.json();
  return {
    captureId: data.purchase_units[0].payments.captures[0].id,
    status: data.status,
    amount: parseFloat(data.purchase_units[0].payments.captures[0].amount.value),
  };
}

// ─────────────────────────────────────────────
// PAYOUTS (Pay Agents)
// ─────────────────────────────────────────────

export async function payoutToAgent(
  agentPaypalEmail: string,
  amount: number,
  taskId: string,
  currency: string = "USD"
) {
  const accessToken = await getAccessToken();

  const payout = {
    sender_batch_header: {
      sender_batch_id: `task_${taskId}_${Date.now()}`,
      email_subject: "You've received payment from AgentMarketplace!",
      email_message: `Payment for completing task #${taskId.slice(0, 8)}`,
    },
    items: [
      {
        recipient_type: "EMAIL",
        amount: {
          value: amount.toFixed(2),
          currency: currency,
        },
        note: `Payment for task #${taskId.slice(0, 8)}`,
        sender_item_id: taskId,
        receiver: agentPaypalEmail,
      },
    ],
  };

  const response = await fetch(`${PAYPAL_API_URL}/v1/payments/payouts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payout),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to create payout: ${error}`);
  }

  const data = await response.json();
  return {
    batchId: data.batch_header.payout_batch_id,
    status: data.batch_header.batch_status,
  };
}

// ─────────────────────────────────────────────
// REFUNDS (Dispute Resolution)
// ─────────────────────────────────────────────

export async function refundPayPalCapture(
  captureId: string,
  amount?: number,
  currency: string = "USD"
) {
  const accessToken = await getAccessToken();

  const refundData: any = {};
  if (amount) {
    refundData.amount = {
      value: amount.toFixed(2),
      currency_code: currency,
    };
  }

  const response = await fetch(
    `${PAYPAL_API_URL}/v2/payments/captures/${captureId}/refund`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(refundData),
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to refund: ${error}`);
  }

  const data = await response.json();
  return {
    refundId: data.id,
    status: data.status,
    amount: parseFloat(data.amount.value),
  };
}

// ─────────────────────────────────────────────
// VERIFICATION
// ─────────────────────────────────────────────

export async function verifyPayPalEmail(email: string): Promise<boolean> {
  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// ─────────────────────────────────────────────
// WEBHOOK VERIFICATION
// ─────────────────────────────────────────────

export async function verifyPayPalWebhook(
  headers: Record<string, string>,
  body: string,
  webhookId: string
): Promise<boolean> {
  const accessToken = await getAccessToken();

  const verificationData = {
    transmission_id: headers["paypal-transmission-id"],
    transmission_time: headers["paypal-transmission-time"],
    cert_url: headers["paypal-cert-url"],
    auth_algo: headers["paypal-auth-algo"],
    transmission_sig: headers["paypal-transmission-sig"],
    webhook_id: webhookId,
    webhook_event: JSON.parse(body),
  };

  const response = await fetch(
    `${PAYPAL_API_URL}/v1/notifications/verify-webhook-signature`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(verificationData),
    }
  );

  if (!response.ok) {
    return false;
  }

  const data = await response.json();
  return data.verification_status === "SUCCESS";
}
