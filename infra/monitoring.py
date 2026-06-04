"""GCP monitoring, alerting, and backup resources for Hermes."""

import pulumi
import pulumi_gcp as gcp


def enable_monitoring_api(project_id: str) -> gcp.projects.Service:
    return gcp.projects.Service(
        "enable-monitoring-googleapis-com",
        project=project_id,
        service="monitoring.googleapis.com",
        disable_on_destroy=False,
    )


def create_weekly_snapshot_policy(region: str) -> gcp.compute.ResourcePolicy:
    return gcp.compute.ResourcePolicy(
        "hermes-weekly-snapshot",
        region=region,
        snapshot_schedule_policy={
            "schedule": {
                "weekly_schedule": {
                    "day_of_weeks": [{"day": "SUNDAY", "start_time": "04:00"}],
                }
            },
            "retention_policy": {"max_retention_days": 14},
        },
    )


def setup_monitoring(
    *,
    project_id: str,
    public_hostname: str,
    alert_email: str,
    billing_account: str,
    budget_usd: float,
) -> list[pulumi.Resource]:
    """Create monitoring resources. Returns resources for dependency ordering."""
    created: list[pulumi.Resource] = []

    monitoring_api = enable_monitoring_api(project_id)
    created.append(monitoring_api)

    if not alert_email:
        pulumi.log.warn(
            "hermes:alert_email not set — skipping uptime and email alerts. "
            "Set with: pulumi config set hermes:alert_email you@example.com"
        )
        return created

    channel = gcp.monitoring.NotificationChannel(
        "hermes-alert-email",
        display_name="Hermes alert email",
        type="email",
        labels={"email_address": alert_email},
        opts=pulumi.ResourceOptions(depends_on=[monitoring_api]),
    )
    created.append(channel)

    if public_hostname:
        uptime = gcp.monitoring.UptimeCheckConfig(
            "hermes-uptime",
            display_name=f"Hermes HTTPS ({public_hostname})",
            timeout="10s",
            period="300s",
            http_check={
                "path": "/",
                "port": 443,
                "use_ssl": True,
                "validate_ssl": True,
                "request_method": "GET",
            },
            monitored_resource={
                "type": "uptime_url",
                "labels": {
                    "project_id": project_id,
                    "host": public_hostname,
                },
            },
            opts=pulumi.ResourceOptions(depends_on=[monitoring_api]),
        )
        created.append(uptime)

        alert = gcp.monitoring.AlertPolicy(
            "hermes-uptime-alert",
            display_name="Hermes HTTPS endpoint down",
            combiner="OR",
            notification_channels=[channel.id],
            conditions=[
                {
                    "display_name": "Uptime check failed",
                    "condition_threshold": {
                        "filter": uptime.uptime_check_id.apply(
                            lambda check_id: (
                                'resource.type = "uptime_url" AND '
                                'metric.type = "monitoring.googleapis.com/uptime_check/check_passed" AND '
                                f'metric.label.check_id = "{check_id}"'
                            )
                        ),
                        "comparison": "COMPARISON_LT",
                        "threshold_value": 1,
                        "duration": "300s",
                        "aggregations": [
                            {
                                "alignment_period": "300s",
                                "per_series_aligner": "ALIGN_FRACTION_TRUE",
                            }
                        ],
                        "trigger": {"count": 1},
                    },
                }
            ],
            alert_strategy={"auto_close": "604800s"},
            opts=pulumi.ResourceOptions(depends_on=[uptime, channel]),
        )
        created.append(alert)

    if billing_account:
        budget = gcp.billing.Budget(
            "hermes-monthly-budget",
            billing_account=billing_account,
            display_name="Hermes GCP monthly budget",
            amount={
                "specified_amount": {
                    "currency_code": "USD",
                    "units": str(int(budget_usd)),
                }
            },
            budget_filter={"projects": [f"projects/{project_id}"]},
            threshold_rules=[
                {"threshold_percent": 0.5},
                {"threshold_percent": 0.9},
                {"threshold_percent": 1.0},
            ],
        )
        created.append(budget)

    return created
