resource "aws_security_group" "alb" {
  count = var.enable_compute ? 1 : 0

  name        = "${var.project_name}-alb"
  description = "ALB ingress from operator CIDR only"
  vpc_id      = aws_vpc.main[0].id

  ingress {
    description = "HTTP API"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr_api != "" ? var.allowed_cidr_api : "127.0.0.1/32"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

resource "aws_security_group" "gpu" {
  count = var.enable_compute ? 1 : 0

  name        = "${var.project_name}-gpu"
  description = "GPU instances - only from ALB"
  vpc_id      = aws_vpc.main[0].id

  ingress {
    description     = "App from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb[0].id]
  }

  dynamic "ingress" {
    for_each = var.allowed_cidr_ssh != "" ? [1] : []
    content {
      description = "SSH from operator"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.allowed_cidr_ssh]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-gpu-sg"
  }
}
