# Spot GPU + ALB. Only when enable_compute=true.
# ASG desired_capacity = 0 by default — scale to 1 only during a live timed session.

# Deep Learning Base AMI: NVIDIA drivers + Docker preinstalled (skips ~20min setup).
data "aws_ami" "gpu_dlami" {
  count = var.enable_compute ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

resource "aws_iam_role" "gpu" {
  count = var.enable_compute ? 1 : 0
  name  = "${var.project_name}-gpu-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "gpu" {
  count = var.enable_compute ? 1 : 0
  name  = "${var.project_name}-gpu-policy"
  role  = aws_iam_role.gpu[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
        Resource = [
          aws_s3_bucket.artifacts[0].arn,
          "${aws_s3_bucket.artifacts[0].arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/${var.project_name}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ec2messages:*", "ssm:UpdateInstanceInformation", "ssmmessages:*"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gpu_ssm" {
  count = var.enable_compute ? 1 : 0

  role       = aws_iam_role.gpu[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "gpu" {
  count = var.enable_compute ? 1 : 0
  name  = "${var.project_name}-gpu-profile"
  role  = aws_iam_role.gpu[0].name
}

resource "aws_subnet" "public_b" {
  count = var.enable_compute ? 1 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = "10.42.2.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available[0].names[1]

  tags = { Name = "${var.project_name}-public-b" }
}

resource "aws_route_table_association" "public_b" {
  count = var.enable_compute ? 1 : 0

  subnet_id      = aws_subnet.public_b[0].id
  route_table_id = aws_route_table.public[0].id
}

# Third AZ for spot GPU capacity (2a/2b often insufficient; AWS often has g4dn in 2c).
resource "aws_subnet" "public_c" {
  count = var.enable_compute ? 1 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = "10.42.3.0/24"
  map_public_ip_on_launch = true
  availability_zone       = data.aws_availability_zones.available[0].names[2]

  tags = { Name = "${var.project_name}-public-c" }
}

resource "aws_route_table_association" "public_c" {
  count = var.enable_compute ? 1 : 0

  subnet_id      = aws_subnet.public_c[0].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_launch_template" "gpu" {
  count = var.enable_compute ? 1 : 0

  name_prefix   = "${var.project_name}-gpu-"
  image_id      = data.aws_ami.gpu_dlami[0].id
  instance_type = var.instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.gpu[0].name
  }

  vpc_security_group_ids = [aws_security_group.gpu[0].id]

  # Model weights + vLLM image need headroom; stock root is too small.
  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = 150
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  # Spot market options live on the ASG mixed_instances_policy (capacity-optimized),
  # not on the launch template, so overrides can pick g4dn or g5.

  user_data = base64encode(templatefile("${path.module}/user_data_gpu.sh.tftpl", {
    aws_region     = var.aws_region
    project_name   = var.project_name
    ecr_registry   = split("/", aws_ecr_repository.serving[0].repository_url)[0]
    ecr_repository = aws_ecr_repository.serving[0].repository_url
    image_param    = aws_ssm_parameter.serving_image.name
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.project_name}-gpu" }
  }

  lifecycle {
    precondition {
      condition     = var.use_spot == true
      error_message = "On-demand GPU forbidden."
    }
    precondition {
      condition     = var.allowed_cidr_api != ""
      error_message = "Set allowed_cidr_api to your public IP/32 before enabling compute."
    }
  }
}

resource "aws_lb_target_group" "gpu" {
  count = var.enable_compute ? 1 : 0

  name     = "${var.project_name}-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main[0].id

  health_check {
    path                = "/health"
    matcher             = "200-399"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb" "api" {
  count = var.enable_compute ? 1 : 0

  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = [aws_subnet.public[0].id, aws_subnet.public_b[0].id, aws_subnet.public_c[0].id]

  enable_deletion_protection = false

  tags = { Name = "${var.project_name}-alb" }
}

resource "aws_lb_listener" "http" {
  count = var.enable_compute ? 1 : 0

  load_balancer_arn = aws_lb.api[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gpu[0].arn
  }
}

resource "aws_autoscaling_group" "gpu" {
  count = var.enable_compute ? 1 : 0

  name                      = "${var.project_name}-gpu-asg"
  min_size                  = 0
  max_size                  = var.asg_max_size
  desired_capacity          = 0
  vpc_zone_identifier       = [aws_subnet.public[0].id, aws_subnet.public_b[0].id, aws_subnet.public_c[0].id]
  health_check_type         = "EC2"
  health_check_grace_period = 120

  # Prefer whichever allowed GPU type has spot capacity across AZs.
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 0
      spot_allocation_strategy                 = "capacity-optimized"
      spot_max_price                           = var.max_spot_price
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.gpu[0].id
        version            = "$Latest"
      }

      override {
        instance_type = "g4dn.xlarge"
      }

      override {
        instance_type = "g5.xlarge"
      }
    }
  }

  target_group_arns = [aws_lb_target_group.gpu[0].arn]

  tag {
    key                 = "Name"
    value               = "${var.project_name}-gpu"
    propagate_at_launch = true
  }

  lifecycle {
    ignore_changes = [desired_capacity]
    precondition {
      condition     = var.use_spot == true
      error_message = "On-demand GPU forbidden."
    }
  }
}

# Scale-out signal for cold-start experiments (queue-depth style can replace later).
resource "aws_autoscaling_policy" "scale_to_one" {
  count = var.enable_compute ? 1 : 0

  name                   = "${var.project_name}-scale-to-one"
  autoscaling_group_name = aws_autoscaling_group.gpu[0].name
  adjustment_type        = "ExactCapacity"
  scaling_adjustment     = 1
  cooldown               = 60
}

resource "aws_cloudwatch_metric_alarm" "gpu_status_check" {
  count = var.enable_compute ? 1 : 0

  alarm_name          = "${var.project_name}-gpu-status-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "GPU instance status check failed"
  treat_missing_data  = "notBreaching"

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.gpu[0].name
  }

  alarm_actions = [aws_sns_topic.budget_alerts.arn]
}
