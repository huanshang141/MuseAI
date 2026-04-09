#!/usr/bin/env python3
"""Analyze performance test results and generate summary report."""
import argparse
import re
from pathlib import Path


def parse_locust_html_report(html_path: str) -> dict:
    """Parse Locust HTML report and extract key metrics.

    The Locust HTML report embeds data in JavaScript.
    We extract the statistics from the minified JS data.
    """
    content = Path(html_path).read_text()

    metrics = {}

    # Locust 2.x embeds stats with snake_case field names
    # Pattern: "name": "endpoint_name", "num_requests": N, "num_failures": M

    # Find all endpoint statistics
    # Pattern matches objects with name, num_requests, num_failures
    # The fields can appear in any order
    endpoint_pattern = r'"name":\s*"([^"]+)"[^}]*"num_requests":\s*(\d+)[^}]*"num_failures":\s*(\d+)'
    endpoint_pattern_alt = r'"name":\s*"([^"]+)"[^}]*"num_failures":\s*(\d+)[^}]*"num_requests":\s*(\d+)'

    endpoints = []
    total_requests = 0
    total_failures = 0

    # Try first pattern (num_requests before num_failures)
    for match in re.finditer(endpoint_pattern, content):
        name = match.group(1)
        requests = int(match.group(2))
        failures = int(match.group(3))

        if name and name != 'None' and name != 'Aggregated':
            endpoints.append({
                'name': name,
                'num_requests': requests,
                'num_failures': failures,
            })
            total_requests += requests
            total_failures += failures

    # Try alternate pattern (num_failures before num_requests)
    for match in re.finditer(endpoint_pattern_alt, content):
        name = match.group(1)
        failures = int(match.group(2))
        requests = int(match.group(3))

        if name and name != 'None':
            # Avoid duplicates
            if not any(e['name'] == name for e in endpoints):
                endpoints.append({
                    'name': name,
                    'num_requests': requests,
                    'num_failures': failures,
                })
                total_requests += requests
                total_failures += failures

    metrics['endpoints'] = endpoints
    metrics['total_requests'] = total_requests
    metrics['total_failures'] = total_failures

    if total_requests > 0:
        metrics['failure_rate'] = (total_failures / total_requests) * 100
    else:
        metrics['failure_rate'] = 0.0

    # Try to extract average response time
    avg_time_pattern = r'"avg_response_time":\s*([\d.]+)'
    avg_times = [float(t) for t in re.findall(avg_time_pattern, content)]
    if avg_times:
        # Filter out very large values (likely from outliers)
        reasonable_times = [t for t in avg_times if t < 10000]
        if reasonable_times:
            metrics['avg_response_time'] = sum(reasonable_times) / len(reasonable_times)

    return metrics


def generate_summary_report(metrics: dict) -> str:
    """Generate a text summary report."""
    report = []
    report.append("=" * 60)
    report.append("Performance Test Summary Report")
    report.append("=" * 60)
    report.append("")

    report.append("Key Metrics:")
    report.append("-" * 40)

    if metrics.get('total_requests'):
        report.append(f"Total Requests: {metrics['total_requests']}")
        report.append(f"Total Failures: {metrics['total_failures']}")
        report.append(f"Failure Rate: {metrics.get('failure_rate', 0):.2f}%")

    if metrics.get('avg_response_time'):
        report.append(f"Average Response Time: {metrics['avg_response_time']:.2f}ms")

    # Per-endpoint breakdown
    if metrics.get('endpoints'):
        report.append("")
        report.append("Per-Endpoint Statistics:")
        report.append("-" * 40)
        for ep in metrics['endpoints']:
            fail_rate = 0 if ep['num_requests'] == 0 else (ep['num_failures'] / ep['num_requests']) * 100
            report.append(f"  {ep['name']}:")
            report.append(f"    Requests: {ep['num_requests']}, Failures: {ep['num_failures']} ({fail_rate:.1f}%)")

    if not metrics or not metrics.get('total_requests'):
        report.append("No metrics found in report")

    report.append("")
    report.append("=" * 60)

    return "\n".join(report)


def analyze_results(report_path: str) -> None:
    """Analyze results and print summary."""
    print(f"\nAnalyzing results from: {report_path}")

    if not Path(report_path).exists():
        print(f"Error: Report file not found: {report_path}")
        return

    metrics = parse_locust_html_report(report_path)
    summary = generate_summary_report(metrics)

    print(summary)

    # Save summary to file
    summary_path = str(Path(report_path).with_suffix('')) + '_summary.txt'
    Path(summary_path).write_text(summary)
    print(f"\nSummary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze performance test results")
    parser.add_argument("report_path", help="Path to Locust HTML report")

    args = parser.parse_args()
    analyze_results(args.report_path)


if __name__ == "__main__":
    main()