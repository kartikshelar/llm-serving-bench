variable "aws_region" {
  type        = string
  description = "Region for all Phase 3 resources. Prefer one region only."
  default     = "us-west-2"
}

variable "project_name" {
  type    = string
  default = "llm-serving-bench"
}

variable "alert_email" {
  type        = string
  description = "Email for AWS Budget and alarm notifications. REQUIRED before apply."
}

variable "budget_limit_usd" {
  type        = number
  description = "AWS Budgets alert threshold. Project hard ceiling is $25; alarm at $15."
  default     = 15

  validation {
    condition     = var.budget_limit_usd <= 15
    error_message = "budget_limit_usd must be <= 15. Hard project ceiling is $25; alarm stays at $15 max."
  }
}

variable "enable_network" {
  type        = bool
  description = "Create public-only VPC. Default false until budget is confirmed."
  default     = false
}

variable "enable_compute" {
  type        = bool
  description = "Create spot GPU + ALB + ASG. COSTS MONEY. Default false."
  default     = false

  validation {
    condition     = !(var.enable_compute && !var.enable_network)
    error_message = "enable_compute requires enable_network = true."
  }
}

variable "use_spot" {
  type        = bool
  description = "Must remain true. On-demand GPU is forbidden."
  default     = true

  validation {
    condition     = var.use_spot == true
    error_message = "use_spot must be true. On-demand GPU is forbidden under the $25 ceiling."
  }
}

variable "instance_type" {
  type        = string
  description = "Allowed spot GPU types only."
  default     = "g4dn.xlarge"

  validation {
    condition     = contains(["g4dn.xlarge", "g5.xlarge"], var.instance_type)
    error_message = "instance_type must be g4dn.xlarge or g5.xlarge."
  }
}

variable "max_spot_price" {
  type        = string
  description = "Spot bid ceiling (USD/hr). Keep low to avoid spike spend."
  default     = "0.30"
}

variable "asg_max_size" {
  type        = number
  description = "Hard cap on GPU instances. Keep at 1 for budget safety."
  default     = 1

  validation {
    condition     = var.asg_max_size == 1
    error_message = "asg_max_size must be 1 under the $25 ceiling."
  }
}

variable "allowed_cidr_ssh" {
  type        = string
  description = "Optional SSH CIDR. Empty disables SSH ingress."
  default     = ""
}

variable "allowed_cidr_api" {
  type        = string
  description = "CIDR allowed to hit the ALB (e.g. your IP/32). Required when compute is enabled."
  default     = ""
}
