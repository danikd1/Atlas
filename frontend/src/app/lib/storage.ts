import { RSSFeed, RSSArticle, Folder, Source } from "../types";

const FEEDS_KEY = "rss_feeds";
const ARTICLES_KEY = "rss_articles";
const FOLDERS_KEY = "rss_folders";
const SOURCES_KEY = "rss_sources";

// Sample feeds and articles for initial state
const sampleFeeds: RSSFeed[] = [
  {
    id: "1",
    title: "Tech News Daily",
    url: "https://technews.example.com/feed",
    description: "Latest technology news and updates",
    addedAt: new Date(2026, 2, 20).toISOString(),
  },
  {
    id: "2",
    title: "Design Inspirations",
    url: "https://design.example.com/rss",
    description: "Creative design articles and tutorials",
    addedAt: new Date(2026, 2, 22).toISOString(),
  },
  {
    id: "3",
    title: "BBC World News",
    url: "http://feeds.bbci.co.uk/news/world/rss.xml",
    description: "World news and current events",
    addedAt: new Date(2026, 2, 21).toISOString(),
  },
  {
    id: "4",
    title: "TechCrunch",
    url: "https://techcrunch.com/feed/",
    description: "Latest technology and startup news",
    addedAt: new Date(2026, 2, 19).toISOString(),
  },
  {
    id: "5",
    title: "The Verge",
    url: "https://www.theverge.com/rss/index.xml",
    description: "Technology, science, art, and culture",
    addedAt: new Date(2026, 2, 18).toISOString(),
  },
  {
    id: "6",
    title: "CSS-Tricks",
    url: "https://css-tricks.com/feed/",
    description: "Web design and development articles",
    addedAt: new Date(2026, 2, 17).toISOString(),
  },
  {
    id: "7",
    title: "Smashing Magazine",
    url: "https://www.smashingmagazine.com/feed/",
    description: "For web designers and developers",
    addedAt: new Date(2026, 2, 16).toISOString(),
  },
  {
    id: "8",
    title: "Hacker News",
    url: "https://news.ycombinator.com/rss",
    description: "Tech news and discussions",
    addedAt: new Date(2026, 2, 15).toISOString(),
  },
];

const sampleArticles: RSSArticle[] = [
  {
    id: "a1",
    feedId: "1",
    feedTitle: "Tech News Daily",
    title: "The Future of AI in Web Development",
    link: "https://technews.example.com/ai-web-dev",
    description: "Exploring how artificial intelligence is transforming the way we build websites and applications.",
    content: `<p>Artificial intelligence is rapidly changing the landscape of web development. From automated code generation to intelligent design systems, AI tools are becoming an integral part of the developer's toolkit.</p>
    
    <p>In this article, we'll explore the latest trends in AI-powered web development tools, including code completion assistants, automated testing frameworks, and design-to-code systems that can transform visual designs into production-ready code.</p>
    
    <p>The future looks bright as these technologies continue to evolve, making web development more accessible while empowering developers to focus on creative problem-solving rather than repetitive tasks.</p>`,
    pubDate: new Date().toISOString(), // Today's article
    author: "Sarah Johnson",
    read: false,
    saved: false,
  },
  {
    id: "a2",
    feedId: "1",
    feedTitle: "Tech News Daily",
    title: "Understanding Modern CSS Grid Layouts",
    link: "https://technews.example.com/css-grid",
    description: "A comprehensive guide to mastering CSS Grid for responsive web design.",
    content: `<p>CSS Grid has revolutionized the way we create layouts on the web. Unlike older techniques like floats and positioning, Grid provides a two-dimensional layout system that makes complex designs simple to implement.</p>
    
    <p>In this comprehensive guide, we'll cover everything from basic grid concepts to advanced techniques like grid template areas, auto-fit, and minmax functions. You'll learn how to create responsive layouts that adapt beautifully to any screen size.</p>
    
    <p>Whether you're building a simple blog or a complex web application, mastering CSS Grid will make your development process faster and more enjoyable.</p>`,
    pubDate: new Date(2026, 2, 26, 14, 15).toISOString(),
    author: "Michael Chen",
    read: false,
    saved: true, // Saved article
  },
  {
    id: "a3",
    feedId: "2",
    feedTitle: "Design Inspirations",
    title: "Color Psychology in UI Design",
    link: "https://design.example.com/color-psychology",
    description: "How to choose the right colors to enhance user experience and communicate your brand message.",
    content: `<p>Color is one of the most powerful tools in a designer's arsenal. The colors you choose for your user interface can dramatically impact how users perceive and interact with your product.</p>
    
    <p>This article explores the psychology behind different colors and how they affect user behavior. We'll look at case studies from successful products and learn how to create color palettes that not only look beautiful but also support your design goals.</p>
    
    <p>From warm colors that create energy and excitement to cool colors that convey trust and professionalism, understanding color psychology will help you make more informed design decisions.</p>`,
    pubDate: new Date(2026, 2, 25, 9, 0).toISOString(),
    author: "Emma Rodriguez",
    read: false,
    saved: false,
  },
  {
    id: "a4",
    feedId: "2",
    feedTitle: "Design Inspirations",
    title: "Minimalist Design Principles for 2026",
    link: "https://design.example.com/minimalism-2026",
    description: "The latest trends in minimalist design and how to apply them to your projects.",
    content: `<p>Minimalism continues to be a dominant force in digital design, but it's evolving. In 2026, we're seeing a shift towards more expressive minimalism that balances simplicity with personality.</p>
    
    <p>This article explores the key principles of modern minimalist design, including strategic use of whitespace, bold typography, subtle animations, and thoughtful color choices. We'll show you how to create designs that are clean and uncluttered while still being engaging and memorable.</p>
    
    <p>Learn how top designers are pushing the boundaries of minimalism to create experiences that are both beautiful and functional.</p>`,
    pubDate: new Date(2026, 2, 24, 16, 45).toISOString(),
    author: "David Park",
    read: false,
    saved: false,
  },
  {
    id: "a5",
    feedId: "1",
    feedTitle: "Tech News Daily",
    title: "Web Performance Optimization in 2026",
    link: "https://technews.example.com/web-performance",
    description: "Essential techniques for building lightning-fast websites that deliver exceptional user experiences.",
    content: `<p>In today's fast-paced digital world, performance is not just a nice-to-have—it's essential. Users expect websites to load instantly, and even a delay of a few seconds can lead to lost conversions and frustrated users.</p>
    
    <p>This comprehensive guide covers the latest performance optimization techniques, including code splitting, lazy loading, image optimization, caching strategies, and server-side rendering. We'll also explore modern tools and frameworks that make performance optimization easier than ever.</p>
    
    <p>By implementing these strategies, you can ensure your website delivers a fast, smooth experience that keeps users engaged and coming back for more.</p>`,
    pubDate: new Date(2026, 2, 23, 11, 20).toISOString(),
    author: "Lisa Anderson",
    read: false,
    saved: false,
  },
  {
    id: "a6",
    feedId: "3",
    feedTitle: "BBC World News",
    title: "Global Climate Summit Reaches Historic Agreement",
    link: "https://bbc.co.uk/news/world-climate-summit",
    description: "World leaders agree on ambitious carbon reduction targets at international climate conference.",
    content: `<p>In a landmark decision, representatives from 195 countries have reached a historic agreement to reduce global carbon emissions by 45% by 2030.</p>
    
    <p>The agreement includes specific commitments from major economies, new funding mechanisms for developing nations, and a framework for monitoring progress. Environmental groups have cautiously welcomed the deal while calling for even more aggressive action.</p>
    
    <p>This summit marks a turning point in international climate policy and sets the stage for transformative changes in energy, transportation, and industrial sectors worldwide.</p>`,
    pubDate: new Date(2026, 2, 31, 10, 30).toISOString(),
    author: "James Wilson",
    read: false,
    saved: false,
  },
  {
    id: "a7",
    feedId: "3",
    feedTitle: "BBC World News",
    title: "Breakthrough in Quantum Computing Research",
    link: "https://bbc.co.uk/news/technology-quantum-computing",
    description: "Scientists achieve major milestone in quantum computing stability and error correction.",
    content: `<p>Researchers at leading universities have announced a significant breakthrough in quantum computing, successfully maintaining stable quantum states for unprecedented durations.</p>
    
    <p>This advancement addresses one of the biggest challenges in quantum computing: error correction. The new technique could accelerate the development of practical quantum computers capable of solving complex problems in medicine, cryptography, and materials science.</p>
    
    <p>Industry experts predict this breakthrough will bring us several years closer to widespread quantum computing applications.</p>`,
    pubDate: new Date(2026, 2, 30, 14, 15).toISOString(),
    author: "Dr. Sarah Mitchell",
    read: false,
    saved: false,
  },
  {
    id: "a8",
    feedId: "3",
    feedTitle: "BBC World News",
    title: "International Space Station Welcomes New Crew",
    link: "https://bbc.co.uk/news/science-space-iss",
    description: "Four astronauts from three countries begin six-month mission aboard the ISS.",
    content: `<p>A multinational crew of four astronauts has successfully docked with the International Space Station, beginning a six-month mission focused on scientific research and station maintenance.</p>
    
    <p>The crew will conduct over 200 experiments ranging from medical research to materials science. This mission includes the first astronaut from Brazil to spend an extended period aboard the ISS.</p>
    
    <p>The successful launch demonstrates continued international cooperation in space exploration despite geopolitical challenges on Earth.</p>`,
    pubDate: new Date(2026, 2, 29, 8, 45).toISOString(),
    author: "Alex Turner",
    read: true,
    saved: false,
  },
  {
    id: "a9",
    feedId: "3",
    feedTitle: "BBC World News",
    title: "New Medical Treatment Shows Promise for Alzheimer's",
    link: "https://bbc.co.uk/news/health-alzheimers-treatment",
    description: "Clinical trials reveal encouraging results for innovative Alzheimer's therapy.",
    content: `<p>A groundbreaking clinical trial has shown promising results for a new treatment approach to Alzheimer's disease, offering hope to millions of patients and families worldwide.</p>
    
    <p>The treatment combines advanced molecular targeting with immunotherapy techniques, showing significant improvement in cognitive function among trial participants. While more research is needed, initial results suggest this could be the most effective Alzheimer's treatment to date.</p>
    
    <p>Medical experts caution that regulatory approval will take time, but the findings represent a major step forward in fighting this devastating disease.</p>`,
    pubDate: new Date(2026, 2, 28, 12, 0).toISOString(),
    author: "Dr. Emily Harris",
    read: true,
    saved: true,
  },
  {
    id: "a10",
    feedId: "3",
    feedTitle: "BBC World News",
    title: "Global Economy Shows Signs of Recovery",
    link: "https://bbc.co.uk/news/business-economy-recovery",
    description: "Major economies report positive growth indicators for first quarter of 2026.",
    content: `<p>Economic data from major economies shows encouraging signs of recovery, with GDP growth exceeding expectations in several regions during the first quarter of 2026.</p>
    
    <p>Analysts attribute the improvement to stabilizing supply chains, controlled inflation, and strong consumer confidence. However, economists warn that challenges remain, including ongoing trade tensions and regional political instability.</p>
    
    <p>The International Monetary Fund has revised its global growth forecast upward following these positive indicators.</p>`,
    pubDate: new Date(2026, 2, 27, 15, 30).toISOString(),
    author: "Robert Chen",
    read: true,
    saved: false,
  },
  // TechCrunch Articles
  {
    id: "a11",
    feedId: "4",
    feedTitle: "TechCrunch",
    title: "AI Startup Raises $200M in Series C Funding",
    link: "https://techcrunch.com/ai-startup-funding-200m",
    description: "Revolutionary AI platform secures major funding round led by top venture capital firms.",
    content: `<p>In one of the largest funding rounds of the year, AI startup IntelliCore has raised $200 million in Series C funding, bringing its total valuation to $1.5 billion.</p>
    
    <p>The company's platform uses advanced machine learning algorithms to help businesses automate complex decision-making processes. Major investors include Sequoia Capital, Andreessen Horowitz, and SoftBank Vision Fund.</p>
    
    <p>IntelliCore plans to use the funding to expand its team, enhance its product offerings, and enter new international markets.</p>`,
    pubDate: new Date(2026, 2, 31, 9, 0).toISOString(),
    author: "Brian Heater",
    read: false,
    saved: false,
  },
  {
    id: "a12",
    feedId: "4",
    feedTitle: "TechCrunch",
    title: "Electric Vehicle Maker Announces New Battery Technology",
    link: "https://techcrunch.com/ev-battery-breakthrough",
    description: "Next-generation batteries promise 500-mile range and 10-minute charging times.",
    content: `<p>Leading electric vehicle manufacturer has unveiled a breakthrough battery technology that could revolutionize the EV industry. The new solid-state batteries offer significantly improved energy density and faster charging capabilities.</p>
    
    <p>The company claims the new batteries will provide a range of over 500 miles on a single charge and can be recharged to 80% capacity in just 10 minutes. Mass production is expected to begin in late 2027.</p>
    
    <p>This development could address two of the main concerns preventing widespread EV adoption: range anxiety and long charging times.</p>`,
    pubDate: new Date(2026, 2, 30, 16, 30).toISOString(),
    author: "Rebecca Bellan",
    read: false,
    saved: true,
  },
  {
    id: "a13",
    feedId: "4",
    feedTitle: "TechCrunch",
    title: "Tech Giants Face New EU Regulations on AI",
    link: "https://techcrunch.com/eu-ai-regulations",
    description: "European Union introduces comprehensive framework for artificial intelligence governance.",
    content: `<p>The European Union has passed sweeping new regulations governing the development and deployment of artificial intelligence technologies. The AI Act establishes strict requirements for high-risk AI systems and bans certain applications deemed too dangerous.</p>
    
    <p>Major technology companies will need to ensure their AI systems comply with transparency requirements, risk assessments, and human oversight provisions. Non-compliance could result in fines of up to 6% of global revenue.</p>
    
    <p>Industry leaders have expressed concerns about the regulations potentially stifling innovation, while consumer advocates praise the emphasis on safety and accountability.</p>`,
    pubDate: new Date(2026, 2, 29, 11, 45).toISOString(),
    author: "Natasha Lomas",
    read: true,
    saved: false,
  },
  {
    id: "a14",
    feedId: "4",
    feedTitle: "TechCrunch",
    title: "Social Media Platform Launches Creator Monetization Tools",
    link: "https://techcrunch.com/social-media-creator-tools",
    description: "New features aim to help content creators earn revenue directly from their audience.",
    content: `<p>A major social media platform has announced a suite of new tools designed to help content creators monetize their work more effectively. The features include subscriptions, tipping, exclusive content, and revenue sharing from ads.</p>
    
    <p>The platform will take only a 10% commission on creator earnings, significantly lower than competitors. Early beta testers report earning potential increases of 300% or more compared to traditional advertising revenue models.</p>
    
    <p>This move is part of a broader trend in the creator economy, with platforms competing to attract and retain top talent by offering better monetization opportunities.</p>`,
    pubDate: new Date(2026, 2, 28, 14, 20).toISOString(),
    author: "Sarah Perez",
    read: true,
    saved: false,
  },
  // The Verge Articles
  {
    id: "a15",
    feedId: "5",
    feedTitle: "The Verge",
    title: "Apple Unveils Next-Generation AR Glasses",
    link: "https://theverge.com/apple-ar-glasses-announcement",
    description: "Long-awaited augmented reality device promises to blend digital and physical worlds.",
    content: `<p>After years of speculation and development, Apple has officially announced its augmented reality glasses. The sleek, lightweight device overlays digital information onto the real world and integrates seamlessly with the Apple ecosystem.</p>
    
    <p>Key features include real-time translation, navigation assistance, contextual information display, and immersive gaming experiences. The glasses use advanced eye-tracking and gesture recognition for intuitive control.</p>
    
    <p>Priced at $1,499, the AR glasses will launch in select markets this fall. Industry analysts predict they could define the future of personal computing, much like the iPhone did in 2007.</p>`,
    pubDate: new Date(2026, 2, 31, 14, 0).toISOString(),
    author: "Dieter Bohn",
    read: false,
    saved: false,
  },
  {
    id: "a16",
    feedId: "5",
    feedTitle: "The Verge",
    title: "NASA's Mars Mission Discovers Evidence of Ancient Water",
    link: "https://theverge.com/nasa-mars-water-discovery",
    description: "Rover findings suggest Mars once had liquid water for extended periods.",
    content: `<p>NASA's Perseverance rover has made a groundbreaking discovery on Mars: clear geological evidence that liquid water existed on the planet's surface for much longer than previously thought.</p>
    
    <p>Analysis of rock samples reveals sedimentary patterns consistent with long-term water flow and deposition. This finding strengthens the possibility that Mars could have supported microbial life in its ancient past.</p>
    
    <p>Scientists are now prioritizing the collection and eventual return of these samples to Earth for more detailed analysis. The discovery has significant implications for our understanding of planetary habitability.</p>`,
    pubDate: new Date(2026, 2, 30, 10, 15).toISOString(),
    author: "Loren Grush",
    read: false,
    saved: true,
  },
  {
    id: "a17",
    feedId: "5",
    feedTitle: "The Verge",
    title: "Gaming Console Wars: Next Generation Begins",
    link: "https://theverge.com/gaming-console-next-gen",
    description: "Major manufacturers announce powerful new gaming systems with innovative features.",
    content: `<p>The gaming industry is entering a new era as major console manufacturers unveil their next-generation systems. Both feature dramatically improved graphics, faster loading times, and innovative controllers with haptic feedback.</p>
    
    <p>Cloud gaming integration allows players to seamlessly switch between console and mobile gaming. Backward compatibility ensures existing game libraries remain playable on the new hardware.</p>
    
    <p>Launch lineups include highly anticipated exclusive titles and enhanced versions of popular games. Pre-orders have already exceeded expectations, suggesting strong consumer demand for the new consoles.</p>`,
    pubDate: new Date(2026, 2, 29, 13, 30).toISOString(),
    author: "Tom Warren",
    read: true,
    saved: false,
  },
  {
    id: "a18",
    feedId: "5",
    feedTitle: "The Verge",
    title: "Streaming Service Announces Major Price Changes",
    link: "https://theverge.com/streaming-service-pricing",
    description: "Popular platform restructures subscription tiers and introduces ad-supported option.",
    content: `<p>One of the world's largest streaming services has announced significant changes to its pricing structure. The company is introducing a more affordable ad-supported tier while slightly increasing prices for ad-free plans.</p>
    
    <p>The new pricing reflects growing competition in the streaming market and rising content production costs. Existing subscribers will have a grace period before the changes take effect.</p>
    
    <p>Industry analysts view this as part of a broader trend toward more flexible, tiered pricing models as streaming platforms seek to balance profitability with subscriber growth.</p>`,
    pubDate: new Date(2026, 2, 28, 15, 45).toISOString(),
    author: "Julia Alexander",
    read: true,
    saved: false,
  },
  // CSS-Tricks Articles
  {
    id: "a19",
    feedId: "6",
    feedTitle: "CSS-Tricks",
    title: "Modern CSS Features You Should Be Using Today",
    link: "https://css-tricks.com/modern-css-features-2026",
    description: "A comprehensive guide to cutting-edge CSS capabilities now supported across browsers.",
    content: `<p>CSS has evolved dramatically in recent years, and many powerful features are now supported across all major browsers. From container queries to cascade layers, these tools can transform how you build layouts.</p>
    
    <p>This article explores the most impactful modern CSS features including :has(), @scope, nesting, and new color functions. We'll look at practical examples and discuss when to use each feature.</p>
    
    <p>By incorporating these techniques into your workflow, you can write cleaner, more maintainable stylesheets while reducing your reliance on JavaScript for common tasks.</p>`,
    pubDate: new Date(2026, 2, 30, 9, 0).toISOString(),
    author: "Chris Coyier",
    read: false,
    saved: false,
  },
  {
    id: "a20",
    feedId: "6",
    feedTitle: "CSS-Tricks",
    title: "Building Accessible Web Components",
    link: "https://css-tricks.com/accessible-web-components",
    description: "Best practices for creating inclusive, ARIA-compliant custom elements.",
    content: `<p>Web components offer powerful encapsulation and reusability, but they require careful consideration to ensure accessibility. This guide covers essential techniques for building components that work for everyone.</p>
    
    <p>We'll explore proper ARIA attributes, keyboard navigation patterns, focus management, and screen reader compatibility. You'll learn how to test your components with assistive technologies and avoid common accessibility pitfalls.</p>
    
    <p>Creating accessible components from the start is easier than retrofitting them later. These practices will help you build inclusive interfaces that serve all users.</p>`,
    pubDate: new Date(2026, 2, 27, 11, 30).toISOString(),
    author: "Sara Soueidan",
    read: false,
    saved: true,
  },
  {
    id: "a21",
    feedId: "6",
    feedTitle: "CSS-Tricks",
    title: "CSS Animation Performance Tips",
    link: "https://css-tricks.com/css-animation-performance",
    description: "How to create smooth, performant animations that don't compromise user experience.",
    content: `<p>Animations can enhance user experience, but poorly optimized animations can cause janky performance and drain battery life. This article teaches you how to create buttery-smooth animations.</p>
    
    <p>We'll cover hardware acceleration, the transform and opacity properties, will-change optimization, and animation debugging tools. You'll learn which properties are safe to animate and which to avoid.</p>
    
    <p>With these techniques, you can create delightful micro-interactions and transitions that feel polished and professional while maintaining excellent performance across all devices.</p>`,
    pubDate: new Date(2026, 2, 25, 14, 15).toISOString(),
    author: "Val Head",
    read: true,
    saved: false,
  },
  // Smashing Magazine Articles
  {
    id: "a22",
    feedId: "7",
    feedTitle: "Smashing Magazine",
    title: "Designing for Neurodiversity: A Practical Guide",
    link: "https://smashingmagazine.com/neurodiversity-design-guide",
    description: "Creating digital experiences that work well for users with diverse cognitive abilities.",
    content: `<p>Neurodiversity encompasses a range of cognitive differences including autism, ADHD, dyslexia, and more. Designing for neurodivergent users benefits everyone by creating clearer, more intuitive interfaces.</p>
    
    <p>This comprehensive guide explores practical strategies like reducing cognitive load, providing clear navigation, offering customization options, and avoiding sensory overload. We'll examine real-world examples from successful products.</p>
    
    <p>By considering neurodiversity in your design process, you create more inclusive digital experiences that accommodate different ways of thinking and processing information.</p>`,
    pubDate: new Date(2026, 2, 31, 8, 30).toISOString(),
    author: "Vitaly Friedman",
    read: false,
    saved: false,
  },
  {
    id: "a23",
    feedId: "7",
    feedTitle: "Smashing Magazine",
    title: "The State of Progressive Web Apps in 2026",
    link: "https://smashingmagazine.com/pwa-state-2026",
    description: "How PWAs have evolved and where they stand in today's development landscape.",
    content: `<p>Progressive Web Apps have matured significantly, with improved browser support and new capabilities that blur the line between web and native applications. This article examines the current state of PWA technology.</p>
    
    <p>We'll explore advanced features like background sync, push notifications, file system access, and offline functionality. You'll learn which PWA features have the best browser support and how to implement them effectively.</p>
    
    <p>For many use cases, PWAs now offer a compelling alternative to native apps, providing a single codebase that works across all platforms while maintaining app-like experiences.</p>`,
    pubDate: new Date(2026, 2, 29, 10, 0).toISOString(),
    author: "Rachel Andrew",
    read: false,
    saved: true,
  },
  {
    id: "a24",
    feedId: "7",
    feedTitle: "Smashing Magazine",
    title: "Typography Best Practices for the Modern Web",
    link: "https://smashingmagazine.com/web-typography-2026",
    description: "Mastering variable fonts, responsive type, and readability optimization.",
    content: `<p>Typography is fundamental to web design, affecting both aesthetics and usability. This guide covers modern best practices for creating beautiful, readable text on any device.</p>
    
    <p>Learn how to leverage variable fonts for maximum flexibility, implement fluid typography that scales smoothly, optimize line length and spacing for readability, and ensure good contrast and accessibility.</p>
    
    <p>With these techniques, you can create typographic systems that look great and enhance the reading experience across all screen sizes and contexts.</p>`,
    pubDate: new Date(2026, 2, 26, 13, 45).toISOString(),
    author: "Oliver Schöndorfer",
    read: true,
    saved: false,
  },
  // Hacker News Articles
  {
    id: "a25",
    feedId: "8",
    feedTitle: "Hacker News",
    title: "Show HN: Open Source Alternative to Figma",
    link: "https://news.ycombinator.com/figma-alternative",
    description: "Community-driven design tool aims to provide free alternative to commercial software.",
    content: `<p>A group of developers has released an open-source design tool that offers many of the features found in commercial products like Figma. The tool runs entirely in the browser and supports real-time collaboration.</p>
    
    <p>Built with modern web technologies, the project has gained significant traction on GitHub with over 15,000 stars in its first month. Contributors are actively adding features and improving performance.</p>
    
    <p>The tool is completely free and can be self-hosted, making it appealing to teams with privacy concerns or budget constraints. The developers plan to add plugin support and additional export options.</p>`,
    pubDate: new Date(2026, 2, 31, 7, 15).toISOString(),
    author: "dang",
    read: false,
    saved: false,
  },
  {
    id: "a26",
    feedId: "8",
    feedTitle: "Hacker News",
    title: "Ask HN: What are you working on?",
    link: "https://news.ycombinator.com/working-on-march-2026",
    description: "Monthly thread where community members share their current projects.",
    content: `<p>This month's "What are you working on?" thread has generated hundreds of responses from the Hacker News community, showcasing diverse projects from machine learning experiments to indie game development.</p>
    
    <p>Popular projects this month include a new programming language designed for system programming, a privacy-focused analytics platform, and a tool for converting technical documentation into interactive tutorials.</p>
    
    <p>These threads provide valuable insights into what developers are building and often lead to collaborations, feedback, and interesting technical discussions.</p>`,
    pubDate: new Date(2026, 2, 30, 12, 0).toISOString(),
    author: "whoishiring",
    read: false,
    saved: false,
  },
  {
    id: "a27",
    feedId: "8",
    feedTitle: "Hacker News",
    title: "WebAssembly Now Supports Garbage Collection",
    link: "https://news.ycombinator.com/wasm-gc-support",
    description: "Major milestone enables efficient language ports to the web platform.",
    content: `<p>The WebAssembly specification has officially added garbage collection support, a highly anticipated feature that will enable more efficient ports of languages like Java, C#, and Python to the web.</p>
    
    <p>Previously, languages with garbage collection had to ship their own GC implementation, adding significant overhead. The new WasmGC proposal allows these languages to integrate with the browser's existing garbage collector.</p>
    
    <p>This development is expected to accelerate WebAssembly adoption and enable new classes of applications to run efficiently in the browser.</p>`,
    pubDate: new Date(2026, 2, 28, 16, 30).toISOString(),
    author: "thunderbong",
    read: true,
    saved: true,
  },
  {
    id: "a28",
    feedId: "8",
    feedTitle: "Hacker News",
    title: "Linux Kernel 6.10 Released with Major Performance Improvements",
    link: "https://news.ycombinator.com/linux-kernel-6-10",
    description: "Latest kernel version brings significant optimizations and new hardware support.",
    content: `<p>The Linux kernel team has released version 6.10, featuring substantial performance improvements for both desktop and server workloads. Benchmarks show up to 20% better throughput in certain scenarios.</p>
    
    <p>Key improvements include enhanced scheduler efficiency, better memory management, and expanded hardware support for the latest processors and GPUs. The release also includes important security fixes and driver updates.</p>
    
    <p>Major distributions are expected to incorporate the new kernel in their upcoming releases, bringing these performance benefits to millions of users.</p>`,
    pubDate: new Date(2026, 2, 27, 9, 45).toISOString(),
    author: "pcr910303",
    read: true,
    saved: false,
  },
];

export const getFeeds = (): RSSFeed[] => {
  const stored = localStorage.getItem(FEEDS_KEY);
  if (stored) {
    return JSON.parse(stored);
  }
  // Initialize with sample data
  localStorage.setItem(FEEDS_KEY, JSON.stringify(sampleFeeds));
  return sampleFeeds;
};

export const saveFeeds = (feeds: RSSFeed[]): void => {
  localStorage.setItem(FEEDS_KEY, JSON.stringify(feeds));
};

export const addFeed = (feed: Omit<RSSFeed, "id" | "addedAt">): RSSFeed => {
  const feeds = getFeeds();
  
  // Check if feed with this URL already exists
  const existingFeed = feeds.find((f) => f.url === feed.url);
  if (existingFeed) {
    // Return existing feed instead of creating a duplicate
    return existingFeed;
  }
  
  const newFeed: RSSFeed = {
    ...feed,
    id: crypto.randomUUID(),
    addedAt: new Date().toISOString(),
  };
  feeds.push(newFeed);
  saveFeeds(feeds);
  return newFeed;
};

export const removeFeed = (feedId: string): void => {
  const feeds = getFeeds().filter((f) => f.id !== feedId);
  saveFeeds(feeds);
  
  // Also remove articles from this feed
  const articles = getArticles().filter((a) => a.feedId !== feedId);
  saveArticles(articles);
};

export const getArticles = (): RSSArticle[] => {
  const stored = localStorage.getItem(ARTICLES_KEY);
  if (stored) {
    return JSON.parse(stored);
  }
  // Initialize with sample data
  localStorage.setItem(ARTICLES_KEY, JSON.stringify(sampleArticles));
  return sampleArticles;
};

export const saveArticles = (articles: RSSArticle[]): void => {
  localStorage.setItem(ARTICLES_KEY, JSON.stringify(articles));
};

export const getArticleById = (id: string): RSSArticle | undefined => {
  return getArticles().find((a) => a.id === id);
};

export const markArticleAsRead = (articleId: string): void => {
  const articles = getArticles();
  const article = articles.find((a) => a.id === articleId);
  if (article) {
    article.read = true;
    saveArticles(articles);
  }
};

export const toggleArticleRead = (articleId: string): void => {
  const articles = getArticles();
  const article = articles.find((a) => a.id === articleId);
  if (article) {
    article.read = !article.read;
    saveArticles(articles);
  }
};

export const toggleArticleSaved = (articleId: string): void => {
  const articles = getArticles();
  const article = articles.find((a) => a.id === articleId);
  if (article) {
    article.saved = !article.saved;
    saveArticles(articles);
  }
};

export const markAllAsRead = (): void => {
  const articles = getArticles();
  articles.forEach((a) => (a.read = true));
  saveArticles(articles);
};

// Folder functions
export const getFolders = (): Folder[] => {
  const stored = localStorage.getItem(FOLDERS_KEY);
  if (stored) {
    return JSON.parse(stored);
  }
  return [];
};

export const saveFolders = (folders: Folder[]): void => {
  localStorage.setItem(FOLDERS_KEY, JSON.stringify(folders));
};

export const addFolder = (name: string, sourceId?: string): Folder => {
  const folders = getFolders();
  const newFolder: Folder = {
    id: crypto.randomUUID(),
    name,
    createdAt: new Date().toISOString(),
    sourceId,
    isSourceFolder: !!sourceId, // true если это папка-источник
  };
  folders.push(newFolder);
  saveFolders(folders);
  return newFolder;
};

export const removeFolder = (folderId: string): void => {
  const folders = getFolders().filter((f) => f.id !== folderId);
  saveFolders(folders);
  
  // Remove folder reference from feeds
  const feeds = getFeeds();
  feeds.forEach((feed) => {
    if (feed.folderId === folderId) {
      feed.folderId = undefined;
    }
  });
  saveFeeds(feeds);
};

export const updateFolderName = (folderId: string, name: string): void => {
  const folders = getFolders();
  const folder = folders.find((f) => f.id === folderId);
  if (folder) {
    folder.name = name;
    saveFolders(folders);
  }
};

export const moveFeedToFolder = (feedId: string, folderId: string | undefined): void => {
  const feeds = getFeeds();
  const feed = feeds.find((f) => f.id === feedId);
  if (feed) {
    feed.folderId = folderId;
    saveFeeds(feeds);
  }
};

// Source functions
export const getSources = (): Source[] => {
  const stored = localStorage.getItem(SOURCES_KEY);
  if (stored) {
    return JSON.parse(stored);
  }
  return [];
};

export const saveSources = (sources: Source[]): void => {
  localStorage.setItem(SOURCES_KEY, JSON.stringify(sources));
};

export const addSource = (source: Omit<Source, "id" | "createdAt">): Source => {
  const sources = getSources();
  const newSource: Source = {
    ...source,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  };
  sources.push(newSource);
  saveSources(sources);
  return newSource;
};

export const removeSource = (sourceId: string): void => {
  const sources = getSources().filter((s) => s.id !== sourceId);
  saveSources(sources);
  
  // Remove all feeds from this source
  const feeds = getFeeds();
  const feedsToRemove = feeds.filter((f) => f.sourceId === sourceId);
  feedsToRemove.forEach((feed) => removeFeed(feed.id));
};

export const getSourceFeeds = (sourceId: string): RSSFeed[] => {
  const feeds = getFeeds();
  return feeds.filter((f) => f.sourceId === sourceId);
};

export const toggleFeedHidden = (feedId: string): void => {
  const feeds = getFeeds();
  const feed = feeds.find((f) => f.id === feedId);
  if (feed) {
    feed.hidden = !feed.hidden;
    saveFeeds(feeds);
  }
};

export const toggleSourceHidden = (sourceId: string): void => {
  const feeds = getFeeds();
  const sourceFeeds = feeds.filter((f) => f.sourceId === sourceId);
  
  if (sourceFeeds.length > 0) {
    // Toggle hidden state for all feeds in this source
    const newHiddenState = !sourceFeeds[0].hidden;
    sourceFeeds.forEach((feed) => {
      feed.hidden = newHiddenState;
    });
    saveFeeds(feeds);
  }
};