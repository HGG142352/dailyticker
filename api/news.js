module.exports = async (req, res) => {
  // CORS Header
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  
  // Edge Caching 헤더 (10분 캐싱)
  // s-maxage=600: Vercel Edge 네트워크에서 600초(10분) 동안 동일 요청에 대한 캐시 유지
  // stale-while-revalidate=30: 캐시 만료 시 최대 30초 동안 구버전 서빙 가능, 백그라운드 재조회 허용
  res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=30');

  if (req.method === 'OPTIONS') return res.status(200).end();

  const ticker = req.query.ticker;
  if (!ticker) {
    return res.status(400).json({ error: 'Missing ticker' });
  }

  const targetUrl = `https://m.stock.naver.com/api/news/stock/${ticker}?pageSize=30&page=1`;
  try {
    const response = await fetch(targetUrl, {
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });
    
    if (!response.ok) throw new Error('Fetch failed');

    const json = await response.json();
    
    if (!json || json.length === 0) {
      return res.status(200).json({ data: [] });
    }

    // 네이버 API는 뉴스들을 블록(그룹) 단위 배열로 내려주므로, 모든 블록의 items를 하나로 합쳐야 합니다.
    let allItems = [];
    json.forEach(block => {
      if (block.items && Array.isArray(block.items)) {
        allItems = allItems.concat(block.items);
      }
    });

    const articles = allItems.map(item => {
      // 날짜 포맷 (YYYYMMDDHHMM -> YYYY-MM-DD HH:MM)
      let dt = item.datetime || "";
      if(dt.length >= 12) {
        dt = `${dt.slice(0,4)}.${dt.slice(4,6)}.${dt.slice(6,8)} ${dt.slice(8,10)}:${dt.slice(10,12)}`;
      }

      return {
        link: item.mobileNewsUrl || `https://finance.naver.com/item/news_read.naver?article_id=${item.articleId}&office_id=${item.officeId}&code=${ticker}`,
        title: item.titleFull || item.title,
        provider: item.officeName,
        date: dt
      };
    });

    return res.status(200).json({ data: articles });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
