#!/usr/bin/env python3
"""Analyze performance test results and generate summary report."""
import argparse
import json
import re
from pathlib import Path


def parse_locust_html_report(html_path: str) -> dict:
    """Parse Locust HTML report and extract key metrics."""
    content = Path(html_path).read_text()

    metrics = {}

    # Extract statistics table data
    # Look for patterns like: "GET /api/v1/health" followed by numbers

    # Find all endpoint statistics
    endpoint_pattern = r'<tr[^>]*>.*?<td[^>]*>([^<]+)</td>.*?</tr>'
    # This is simplified - in real implementation, use BeautifulSoup or similar

    # Extract summary statistics
    total_requests_match = re.search(r'Total Requests.*?(\d+)', content, re.DOTALL)
    if total_requests_match:
        metrics['total_requests'] = int(total_requests_match.group(1))

    fail_rate_match = re.search(r'Failure Rate.*?([\d.]+)%', content, re.DOTALL)
    if fail_rate_match:
        metrics['failure_rate'] = float(fail_rate_match.group(1))

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

    if 'total_requests' in metrics:
        report.append(f"Total Requests: {metrics['total_requests']}")

    if 'failure_rate' in metrics:
        report.append(f"Failure Rate: {metrics['failure_rate']:.2f}%")

    report.append("")
    report.append("=" * 60)

    return "\n".join(report)


def analyze_results(report_path: str) -> None:
    """Analyze results and print summary."""
    print(f"\nAnalyzing results from: {report_path}")

    metrics = parse_locust_html_report(report_path)
    summary = generate_summary_report(metrics)

    print(summary)

    # Save summary to file
    summary_path = report_path.replace('.html', '_summary.txt')
    Path(summary_path).write_text(summary)
    print(f"\nSummary saved to: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Analyze performance test results")
    parser.add_argument("report_path", help="Path to Locust HTML report")

    args = parser.parse_args()
    analyze_results(args.report_path)


if __name__ == "__main__":
    main()
