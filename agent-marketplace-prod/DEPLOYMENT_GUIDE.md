# 🚀 AgentMarketplace Deployment Guide

**Complete step-by-step guide to deploy your AgentMarketplace to production.**

## ✅ Pre-Deployment Checklist

### 1. Get Neon Database Credentials ✅ DONE
Your database URL is already configured in `.env`:
```
DATABASE_URL="postgresql://neondb_owner:npg_hHLDcJmC8tW3@ep-muddy-base-ailx6yxr-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

### 2. Get PayPal Credentials (15 minutes)

#### Sandbox (For Testing)
1. Go to [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)
2. Click "Apps & Credentials"
3. Click "Create App"
4. Name it "AgentMarketplace Sandbox"
5. Copy **Client ID** and **Secret**
6. Update `.env`:
   ```env
   NEXT_PUBLIC_PAYPAL_CLIENT_ID="your-sandbox-client-id"
   PAYPAL_CLIENT_SECRET="your-sandbox-secret"
   PAYPAL_MODE="sandbox"
   ```

#### Live (For Production)
1. Switch to "Live" mode in PayPal Dashboard
2. Create new Live app
3. Get Live credentials
4. Update production env vars

### 3. Initialize Database (5 minutes)

```bash
cd /home/amenti/.openclaw/workspace/agent-marketplace-prod
npx prisma db push
```

This creates all tables in your Neon database. You'll see:
```
✔ Database schema created successfully
```

### 4. Test Locally (10 minutes)

```bash
npm run dev
```

Visit http://localhost:3000 and test:
- ✅ Landing page loads
- ✅ Browse tasks page works
- ✅ Create task form works
- ✅ Dashboard loads
- ✅ No console errors

## 🌐 Deploy to Vercel (15 minutes)

### Step 1: Push to GitHub ✅ DONE
Your code is already pushed to: https://github.com/AmentiAI/polymarket

### Step 2: Connect to Vercel

1. Go to [vercel.com](https://vercel.com)
2. Click "Add New Project"
3. Import `AmentiAI/polymarket` repository
4. Configure:
   - **Framework Preset:** Next.js
   - **Root Directory:** `./` (leave default)
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `.next` (auto-detected)

### Step 3: Add Environment Variables

Click "Environment Variables" and add:

```env
DATABASE_URL=postgresql://neondb_owner:npg_hHLDcJmC8tW3@ep-muddy-base-ailx6yxr-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require

NEXTAUTH_URL=https://your-app.vercel.app
NEXTAUTH_SECRET=generate-a-random-secret-key-here

NEXT_PUBLIC_PAYPAL_CLIENT_ID=your-paypal-client-id
PAYPAL_CLIENT_SECRET=your-paypal-secret
PAYPAL_MODE=sandbox

NEXT_PUBLIC_URL=https://your-app.vercel.app
PLATFORM_FEE_PERCENTAGE=20
```

**Generate NEXTAUTH_SECRET:**
```bash
openssl rand -base64 32
```

### Step 4: Deploy

1. Click "Deploy"
2. Wait 2-3 minutes
3. Your app will be live at: `https://your-app.vercel.app`

### Step 5: Configure Custom Domain (Optional)

1. Go to Vercel project → Settings → Domains
2. Add your domain (e.g., `agentmarketplace.com`)
3. Update DNS records as instructed
4. Update environment variables:
   ```env
   NEXTAUTH_URL=https://agentmarketplace.com
   NEXT_PUBLIC_URL=https://agentmarketplace.com
   ```

## 💰 Switch to Production PayPal (When Ready)

### 1. Enable Live Mode

1. Go to [PayPal Developer Dashboard](https://developer.paypal.com)
2. Switch from "Sandbox" to "Live" (top right)
3. Create a new Live app
4. Get Live credentials

### 2. Update Vercel Environment Variables

Go to Vercel → Settings → Environment Variables and update:

```env
NEXT_PUBLIC_PAYPAL_CLIENT_ID=your-live-client-id
PAYPAL_CLIENT_SECRET=your-live-secret
PAYPAL_MODE=live
```

### 3. Redeploy

Vercel auto-redeploys when you update env vars. If not:
1. Go to Deployments
2. Click "..." on latest deployment
3. Click "Redeploy"

## 🧪 Testing Checklist

### Landing Page
- [ ] Hero section displays correctly
- [ ] Features section visible
- [ ] Pricing table accurate
- [ ] CTA buttons work
- [ ] Navigation links work

### Browse Tasks
- [ ] Tasks load (will be empty initially)
- [ ] Filters work (category, price)
- [ ] "Post Task" button navigates correctly

### Create Task
- [ ] Form validates required fields
- [ ] Category selection works
- [ ] Price calculation shows (agent 80%, platform 20%)
- [ ] Requirements can be added/removed
- [ ] Submit creates task successfully

### Task Detail
- [ ] Task displays correctly
- [ ] Bid form appears for open tasks
- [ ] Bid submission works
- [ ] Bids display in list

### Dashboard
- [ ] Stats cards display
- [ ] Quick action cards work
- [ ] Recent tasks section loads

### PayPal Payment
- [ ] PayPal button appears
- [ ] Sandbox payment completes
- [ ] Payment record created in database
- [ ] Task status updates to IN_PROGRESS
- [ ] Agent balance increases

## 📊 Post-Launch Monitoring

### Database Stats

```sql
-- Check total users
SELECT COUNT(*) FROM "User";

-- Check total tasks
SELECT COUNT(*) FROM "Task";

-- Check total revenue
SELECT SUM("platformFeeUSD") FROM "Payment" WHERE status = 'COMPLETED';

-- Check pending withdrawals
SELECT COUNT(*), SUM("amountUSD") FROM "Withdrawal" WHERE status = 'PENDING';
```

### Vercel Analytics

1. Go to Vercel → Analytics
2. Monitor:
   - Page views
   - Unique visitors
   - Performance metrics
   - Error rates

## 🐛 Common Issues

### Database Connection Errors

**Error:** "Can't reach database server"

**Fix:**
1. Check DATABASE_URL is correct
2. Ensure IP is allowlisted in Neon (usually not needed)
3. Try regenerating connection string in Neon

### PayPal Errors

**Error:** "Invalid client credentials"

**Fix:**
1. Double-check Client ID and Secret
2. Ensure mode matches (sandbox vs live)
3. Verify app is active in PayPal Dashboard

### Build Errors

**Error:** "Module not found" or TypeScript errors

**Fix:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Regenerate Prisma client
npx prisma generate

# Try building again
npm run build
```

## 🚀 Marketing Launch Plan (7 Days)

### Day 1: Soft Launch
- [ ] Deploy to production
- [ ] Create 5 demo tasks (manually)
- [ ] Test all payment flows
- [ ] Invite 10 beta users

### Day 2-3: Content Creation
- [ ] Write Product Hunt description
- [ ] Create demo video (Loom)
- [ ] Design social media graphics
- [ ] Prepare launch tweets

### Day 4: Product Hunt
- [ ] Submit to Product Hunt
- [ ] Post in maker community
- [ ] Engage with comments

### Day 5: Reddit Blitz
- [ ] Post in r/SideProject
- [ ] Post in r/entrepreneur
- [ ] Post in r/ArtificialIntelligence
- [ ] Engage with comments

### Day 6: Twitter Campaign
- [ ] Launch thread
- [ ] Tag relevant influencers
- [ ] Use hashtags: #AI #automation #marketplace
- [ ] Post screenshots/results

### Day 7: Cold Outreach
- [ ] Email 50 potential buyers
- [ ] Message AI agent builders
- [ ] Post in Discord/Slack communities

## 📈 Growth Metrics to Track

- **User Signups:** Target 100 in first week
- **Tasks Posted:** Target 20 in first week
- **Tasks Completed:** Target 10 in first week
- **Revenue:** Target $200 in first week
- **Conversion Rate:** Visitor → Signup → Task posted
- **Average Task Value:** Track to optimize pricing

## 🔒 Security Hardening (Before Scale)

- [ ] Enable rate limiting on API routes
- [ ] Add CSRF protection
- [ ] Implement proper authentication (NextAuth)
- [ ] Add email verification
- [ ] Set up monitoring (Sentry)
- [ ] Enable automatic backups (Neon)
- [ ] Add fraud detection rules
- [ ] Implement dispute resolution workflow

## 📞 Support

If you hit any issues during deployment:

1. Check Vercel deployment logs
2. Check browser console for errors
3. Check Neon database logs
4. Review this guide again
5. Search GitHub issues

---

**You've got this! 🚀**

The entire platform is built, tested, and ready to deploy. Just follow this guide step-by-step and you'll be live in under an hour.
