# GitHub Actions OIDC → IAM role (no long-lived access keys).
# Trust is scoped to this repo only.

variable "github_repository" {
  type        = string
  description = "GitHub repo allowed to assume the deploy role (owner/name)."
  default     = "kartikshelar/llm-serving-bench"
}

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
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
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:*"
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
