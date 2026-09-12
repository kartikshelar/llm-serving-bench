# AWS budget guardrails (Phase 3) — NON-NEGOTIABLE

**Hard ceiling: $25 USD total for this entire project.**  
**Alarm: $15 actual spend** (email).  
If you are approaching $15, **stop and destroy**. Do not “finish one more run.”

This file is the checklist. Do the steps **in order**. Skipping is how bills blow up.

---

## Before any `terraform apply` that creates network/GPU/ALB

### 1. Account + billing
- [ ] Personal AWS account (not Academy Learner Lab — no GPU there)
- [ ] Root email you check daily
- [ ] MFA on root
- [ ] Billing alerts enabled in Billing preferences

### 2. Create the $15 budget (console) — do this TODAY before infra
AWS Console → **Billing** → **Budgets** → Create budget:

| Field | Value |
|---|---|
| Type | Cost budget |
| Period | Monthly (or custom “reset” each project month) |
| Amount | **15.00 USD** |
| Scope | All AWS services, linked account |
| Alert 1 | Actual ≥ **50%** ($7.50) → your email |
| Alert 2 | Actual ≥ **80%** ($12) → your email |
| Alert 3 | Actual ≥ **100%** ($15) → your email |
| Alert 4 | Forecasted ≥ **$20** → your email |

Also set a **second** budget or note: hard personal stop at **$25** even if AWS does not cut you off automatically. AWS Budgets **notify**; they do **not** always stop spend by themselves unless you add Budget Actions (optional later).

### 3. Verify pricing (before GPU on)
Check current **spot** price for `g4dn.xlarge` in your region (e.g. `us-west-2`):

```powershell
aws ec2 describe-spot-price-history --instance-types g4dn.xlarge --product-descriptions "Linux/UNIX" --start-time (Get-Date).ToUniversalTime().AddHours(-1).ToString("o") --region us-west-2
```

Rough session math (example only — verify live):
- Spot GPU ~$0.20/hr × 3 hr = $0.60
- ALB ~$0.023/hr × 3 hr ≈ $0.07
- S3/ECR pennies  
→ One careful session should be **well under $2**. Overnight GPU+ALB can burn the whole $25.

---

## Terraform safety switches (this repo)

| Variable | Default | Meaning |
|---|---|---|
| `enable_network` | `false` | VPC / subnet / SG |
| `enable_compute` | `false` | Spot GPU + ALB + ASG — **costs money** |
| `use_spot` | `true` (frozen) | On-demand is **rejected** by validation |
| `max_spot_price` | low cap | Bid ceiling so you don’t pay surprise spikes |

**Rule:** first apply should be **budget resources only** (or with both enables `false`).  
Only set `enable_compute=true` for a short live session, then `terraform destroy`.

---

## Every live session (mandatory)

```text
1. Confirm Budgets email works (or check Billing → Budgets)
2. terraform apply  (compute on only if needed)
3. Run measurements
4. terraform destroy   ← NO EXCEPTIONS
5. Confirm EC2=0, ALB=0, NAT=0, Elastic IPs=0 in console
```

Never leave overnight. Never “I’ll destroy tomorrow.”

---

## Forbidden (will blow the budget)

- NAT Gateway
- On-demand GPU
- Leaving ALB up with no instance (still ~$16+/month)
- Idle EBS volumes after destroy failures
- Multi-region experiments
- “Just try g5.xlarge for fun”

---

## What Phase 3 is allowed to spend on

Within **$25 total**:
- Spot `g4dn.xlarge` (preferred) for a few hours across sessions
- Short-lived ALB
- ECR + small S3
- CloudWatch (keep alarms cheap; avoid high-resolution custom metrics spam)

If cumulative bill hits **$15**, Phase 3 stops. Write up with whatever `aws_*` rows you have. Kaggle already proved the ladder.
