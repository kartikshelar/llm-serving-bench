# GitHub Actions OIDC → IAM role (no long-lived access keys).
# Trust is scoped to this repo only.

variable "github_repository" {
  type        = string
  description = "GitHub repo allowed to assume the deploy role (owner/name)."
  default     = "kartikshelar/llm-serving-bench"
}

# Repos created after 2026-07-15 use immutable OIDC sub claims:
#   repo:owner@OWNER_ID/name@REPO_ID:ref:...
# Get prefix: gh api repos/OWNER/NAME/actions/oidc/customization/sub --jq .sub_claim_prefix
variable "github_oidc_sub_prefix" {
  type        = string
  description = "Exact OIDC sub claim prefix from GitHub (immutable IDs)."
  default     = "repo:kartikshelar@71000941/llm-serving-bench@1360824412"
}

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  # Ignored for github.com (AWS trusts GitHub's CA); API still requires a value.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "${var.github_oidc_sub_prefix}:*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions" {
  name = "${var.project_name}-github-actions"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRAuth"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:DescribeRepositories"
        ]
        Resource = try(aws_ecr_repository.serving[0].arn, "*")
      },
      {
        Sid    = "PublishImageUri"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:GetParameter"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/*"
      },
      {
        Sid    = "DeployRefresh"
        Effect = "Allow"
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:StartInstanceRefresh",
          "autoscaling:DescribeInstanceRefreshes",
          "ec2:DescribeInstances",
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommands"
        ]
        Resource = "*"
      }
    ]
  })
}

# Image URI written by CI; GPU nodes and deploy steps read it.
resource "aws_ssm_parameter" "serving_image" {
  name  = "/${var.project_name}/serving_image"
  type  = "String"
  value = "placeholder:not-pushed-yet"

  lifecycle {
    ignore_changes = [value]
  }
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "Set this as GitHub Actions secret/variable AWS_ROLE_ARN."
}

output "serving_image_param" {
  value = aws_ssm_parameter.serving_image.name
}
