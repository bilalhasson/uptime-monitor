from notifications.email import send_email


def send_monitor_added_email(monitor):
    send_email(
        user=monitor.owner,
        subject=f"Monitor added: {monitor.url}",
        body=(
            f"You're now monitoring {monitor.url}.\n\n"
            f"We'll check it every {monitor.check_interval} seconds and notify you "
            f"if it goes down."
        ),
        category="monitor_added",
        category_label="Monitor added",
    )


def send_monitor_down_email(monitor):
    send_email(
        user=monitor.owner,
        subject=f"ALERT: {monitor.url} is DOWN",
        body=(
            f"Your monitor for {monitor.url} is now DOWN.\n\n"
            f"Last checked at: {monitor.last_checked_at}\n\n"
            "We'll notify you when it recovers."
        ),
        category="monitor_down",
        category_label="Monitor goes down",
    )


def send_monitor_recovery_email(monitor):
    send_email(
        user=monitor.owner,
        subject=f"RECOVERED: {monitor.url} is back UP",
        body=(
            f"Your monitor for {monitor.url} has RECOVERED and is back UP.\n\n"
            f"Last checked at: {monitor.last_checked_at}"
        ),
        category="monitor_recovered",
        category_label="Monitor recovers",
    )


def send_ssl_expiring_email(monitor, days_remaining):
    send_email(
        user=monitor.owner,
        subject=f"SSL certificate expiring soon: {monitor.url}",
        body=(
            f"The SSL certificate for {monitor.url} expires in {days_remaining} days.\n\n"
            f"Expiry date: {monitor.ssl_expiry_date}\n"
            f"Issuer: {monitor.ssl_issuer}\n\n"
            "Please renew the certificate to avoid service disruption."
        ),
        category="ssl_expiring",
        category_label="SSL certificate expiring",
    )
