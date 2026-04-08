// Catalog of available RSS sources with multiple feeds
export interface FeedData {
  title: string;
  url: string;
  description: string;
  category: string;
}

export interface SourceData {
  name: string;
  domain: string;
  feeds: FeedData[];
}

// Map источников с несколькими лентами
export const sourceFeeds: Record<string, SourceData> = {
  "techcrunch.com": {
    name: "TechCrunch",
    domain: "techcrunch.com",
    feeds: [
      {
        title: "TechCrunch - All Posts",
        url: "https://techcrunch.com/feed/",
        description: "Latest technology and startup news",
        category: "Technology",
      },
      {
        title: "TechCrunch - Startups",
        url: "https://techcrunch.com/category/startups/feed/",
        description: "Startup news and funding",
        category: "Startups",
      },
      {
        title: "TechCrunch - AI",
        url: "https://techcrunch.com/category/artificial-intelligence/feed/",
        description: "Artificial Intelligence news",
        category: "AI",
      },
    ],
  },
  "bbc.co.uk": {
    name: "BBC News",
    domain: "bbc.co.uk",
    feeds: [
      {
        title: "BBC World News",
        url: "http://feeds.bbci.co.uk/news/world/rss.xml",
        description: "World news and current events",
        category: "News",
      },
      {
        title: "BBC Technology",
        url: "http://feeds.bbci.co.uk/news/technology/rss.xml",
        description: "Technology news",
        category: "Technology",
      },
      {
        title: "BBC Science",
        url: "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        description: "Science and environment news",
        category: "Science",
      },
    ],
  },
  "theverge.com": {
    name: "The Verge",
    domain: "theverge.com",
    feeds: [
      {
        title: "The Verge - All Posts",
        url: "https://www.theverge.com/rss/index.xml",
        description: "Technology, science, art, and culture",
        category: "Technology",
      },
      {
        title: "The Verge - Tech",
        url: "https://www.theverge.com/tech/rss/index.xml",
        description: "Tech news and reviews",
        category: "Technology",
      },
    ],
  },
};

// Функция для получения доменной части URL
export function getDomainFromUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch {
    return '';
  }
}

// Функция для получения информации об источнике по URL ленты
export function getSourceByFeedUrl(feedUrl: string): SourceData | null {
  const domain = getDomainFromUrl(feedUrl);
  return sourceFeeds[domain] || null;
}

// Функция для получения количества лент у источника по URL
export function getFeedCountByUrl(feedUrl: string): number {
  const source = getSourceByFeedUrl(feedUrl);
  return source ? source.feeds.length : 0;
}
