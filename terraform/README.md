# Terraform (Phase 3)

**Hard ceiling: $25 total. Alarm: $15. Spot only. No NAT. Destroy every session.**

Read [`docs/aws-budget-guardrails.md`](../docs/aws-budget-guardrails.md) before anything else.

## Safety defaults

| Flag | Default | Effect |
|---|---|---|
| `enable_network` | `false` | No VPC |
| `enable_compute` | `false` | No GPU / ALB / ASG |
| `use_spot` | `true` (validated) | On-demand rejected |
| `asg_max_size` | `1` (validated) | Cannot scale past 1 |
| `budget_limit_usd` | `15` (max 15) | Cannot set alarm above $15 |

ASG `desired_capacity` starts at **0** even when compute is enabled.

## First apply (budget only)

```powershell
cd terraform
copy terraform.tfvars.example terraform.tfvars
# edit alert_email=
..\scripts\aws_preflight.ps1
terraform init
terraform plan
terraform apply
```

Then confirm the **SNS subscription email** and that Billing → Budgets shows the $15 budget.

## Later (short live session only)

1. Set `enable_network=true` (still no GPU)
2. Apply, verify
3. Set `enable_compute=true` + `allowed_cidr_api="YOUR.IP/32"`
4. Run `..\scripts\aws_preflight.ps1 -AllowNetwork -AllowCompute`
5. Apply, scale ASG to 1, measure, **immediately**:
   ```powershell
   terraform destroy
   ```
6. Console-check: EC2=0, ALB=0, NAT=0, unattached EBS=0, Elastic IPs=0

## Forbidden

- NAT Gateway
- On-demand GPU
- `asg_max_size > 1`
- Leaving ALB up overnight

## Region note (spot capacity)

`us-west-2` has Spot G/VT quota (=4) but often **no g4dn/g5 spot capacity**.
Pending quota requests (desired **4**) for a move:

| Region | Quota code | Request id (prefix) |
|---|---|---|
| `us-east-1` | `L-3819A6DF` | `6ec7332e…` |
| `us-east-2` | `L-3819A6DF` | `ddd44629…` |

Check status:

```powershell
aws service-quotas get-requested-service-quota-change --request-id <id> --region us-east-1
# or
aws service-quotas list-requested-service-quota-change-history-by-quota --service-code ec2 --quota-code L-3819A6DF --region us-east-1
```

When **APPROVED** in one east region: set `aws_region` in `terraform.tfvars`, keep `enable_compute=false`, destroy leftover `us-west-2` network if you are abandoning it, then `terraform apply` for network-only in the new region. Do **not** enable compute until a short live session.
