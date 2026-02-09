import logging
from radar.connectors.knowhow_feed import _parse_rss_with_feedparser
from radar.integrations.slack import send_to_slack

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting daily keyword search...")

    # Example: Fetch RSS feed data
    rss_data = """<rss>...</rss>"""  # Replace with actual RSS feed fetching logic
    parsed_data = _parse_rss_with_feedparser(rss_data)

    # Filter data based on keywords
    keywords = ["example", "keyword"]
    filtered_results = [item for item in parsed_data if any(kw in item['title'] for kw in keywords)]

    # Send results to Slack
    for result in filtered_results:
        message = f"Title: {result['title']}\nURL: {result['url']}\nPublished: {result['published_at']}"
        send_to_slack(message)

if __name__ == "__main__":
    main()