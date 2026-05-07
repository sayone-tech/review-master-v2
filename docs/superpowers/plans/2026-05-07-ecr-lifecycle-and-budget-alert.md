# ECR Lifecycle Policy + AWS Budget Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Keep ECR image storage lean by expiring untagged images quickly and capping tagged image history, and alert via email before the AWS monthly bill surprises anyone.

**Architecture:** Two Terraform-only changes — update `ecr.tf` with a two-rule lifecycle policy (untagged → expire after 1 day, tagged → keep last 10), and add a new `budgets.tf` with an `aws_budgets_budget` resource wired to the existing `alert_email` variable. No application code is touched.

**Tech Stack:** Terraform ~> 5.0 AWS provider, `aws_ecr_lifecycle_policy`, `aws_budgets_budget`

---

## File Map

| File | Change |
|------|--------|
| `deployment/terraform/ecr.tf` | Modify — replace single-rule lifecycle policy with two-rule policy |
| `deployment/terraform/budgets.tf` | Create — monthly cost budget with 80% and 100% alert thresholds |

---

### Task 1: Improve ECR Lifecycle Policy

The current policy uses `tagStatus = "any"` with a count of 10. This means untagged images from cancelled or failed builds count against the 10 slots and can push out real releases. The fix is two explicit rules: purge untagged images after 1 day, keep the last 10 tagged images.

**Files:**
- Modify: `deployment/terraform/ecr.tf`

- [x] **Step 1: Open `deployment/terraform/ecr.tf` and replace the lifecycle policy**

The current policy block:

```hcl
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
```

Replace with:

```hcl
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep last 10 tagged releases"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = [""]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      },
    ]
  })
}
```

- [x] **Step 2: Validate**

Run from `deployment/terraform/`:
```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 3: Commit**

```bash
git add deployment/terraform/ecr.tf
git commit -m "feat(terraform): improve ECR lifecycle — expire untagged in 1d, keep 10 tagged"
```

---

### Task 2: Add AWS Budget Alert

Create a monthly cost budget for the account. Actual spend is ~$50/month (EC2 t4g.medium ~$28, RDS db.t4g.micro ~$15, S3 + misc ~$7). The budget limit is set at $70 — $20 above actual spend — so alerts only fire when costs spike unexpectedly, not every month as a matter of course.

Two alert thresholds:
- **80% forecasted** — early warning while there's still time to act
- **100% actual** — you've hit the limit

Both alerts email `alert_email` (already defined in `variables.tf` as `renjith@sayonetech.com`).

**Files:**
- Create: `deployment/terraform/budgets.tf`

- [x] **Step 1: Create `deployment/terraform/budgets.tf`**

```hcl
resource "aws_budgets_budget" "monthly" {
  name         = "review-master-monthly"
  budget_type  = "COST"
  limit_amount = "70"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
```

- [x] **Step 2: Validate**

```bash
terraform validate
```
Expected: `Success! The configuration is valid.`

- [x] **Step 3: Commit**

```bash
git add deployment/terraform/budgets.tf
git commit -m "feat(terraform): add monthly AWS budget alert at 80% forecast and 100% actual"
```

---

### Task 3: Apply and Verify

- [x] **Step 1: Plan — confirm only expected resources**

```bash
cd deployment/terraform
terraform plan -var-file=terraform.tfvars
```

Expected plan output — exactly these two changes, nothing else:

```
# aws_budgets_budget.monthly will be created
# aws_ecr_lifecycle_policy.app will be updated in-place
```

If anything else appears, stop and investigate before applying.

- [x] **Step 2: Apply**

```bash
terraform apply -var-file=terraform.tfvars
```

Type `yes`. Expected: `Apply complete! Resources: 1 added, 1 changed, 0 destroyed.`

- [x] **Step 3: Verify ECR lifecycle in AWS Console**

Open **AWS Console → ECR → review-master/app → Lifecycle policy**.

Confirm two rules are shown:
- Priority 1: Expire untagged after 1 day
- Priority 2: Keep last 10 tagged

- [x] **Step 4: Verify Budget in AWS Console**

Open **AWS Console → Billing → Budgets → review-master-monthly**.

Confirm:
- Budget limit: $100.00 USD / Monthly
- Two notifications listed (80% forecasted, 100% actual)
- Subscriber email: `renjith@sayonetech.com`

> **Note:** AWS Budgets sends a confirmation email to the subscriber address when the budget is first created — click the link in that email to confirm the subscription, otherwise alerts won't be delivered.

- [x] **Step 5: Final commit (if any last-minute fixes)**

```bash
git status  # should be clean
```
