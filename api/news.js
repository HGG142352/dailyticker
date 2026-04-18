module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  if (req.method === 'OPTIONS') return res.status(200).end();

  const ticker = req.query.ticker;
  if (!ticker) {
    return res.status(400).json({ error: 'Missing ticker' });
  }

  const targetUrl = `https://finance.naver.com/item/news_news.naver?code=${ticker}&page=1`;
  try {
    const response = await fetch(targetUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });
    
    if (!response.ok) throw new Error('Fetch failed');

    const buffer = await response.arrayBuffer();
    const decoder = new TextDecoder('euc-kr');
    const html = decoder.decode(buffer);

    // 단순 정규식을 사용한 HTML 파싱
    const articles = [];
    const titleRegex = /<td class="title">\s*<a href="([^"]+)"[^>]*>([^<]+)<\/a>\s*<\/td>/g;
    const infoRegex = /<td class="info">([^<]+)<\/td>/g;
    const dateRegex = /<td class="date">([^<]+)<\/td>/g;

    let titleMatch, infoMatch, dateMatch;

    while ((titleMatch = titleRegex.exec(html)) !== null) {
      infoMatch = infoRegex.exec(html);
      dateMatch = dateRegex.exec(html);

      if (infoMatch && dateMatch) {
        let link = ("https://finance.naver.com" + titleMatch[1]).replace(/&amp;/g, '&');
        articles.push({
          link: link,
          title: titleMatch[2].trim(),
          provider: infoMatch[1].trim(),
          date: dateMatch[1].trim()
        });
      }
    }

    return res.status(200).json({ data: articles.slice(0, 10) });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
