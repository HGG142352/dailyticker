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
  const targetUrl = `https://m.stock.naver.com/api/news/stock/${ticker}?pageSize=100&page=1`;
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
      let dateObj = null;
      if(dt.length >= 12) {
        dateObj = new Date(`${dt.slice(0,4)}-${dt.slice(4,6)}-${dt.slice(6,8)}T${dt.slice(8,10)}:${dt.slice(10,12)}:00`);
        dt = `${dt.slice(0,4)}.${dt.slice(4,6)}.${dt.slice(6,8)} ${dt.slice(8,10)}:${dt.slice(10,12)}`;
      }

      return {
        link: item.mobileNewsUrl || `https://finance.naver.com/item/news_read.naver?article_id=${item.articleId}&office_id=${item.officeId}&code=${ticker}`,
        title: item.titleFull || item.title,
        provider: item.officeName,
        date: dt,
        timestamp: dateObj ? dateObj.getTime() : 0
      };
    });

    // --- 기사 제목 기반 증권사 리포트/의견 분석 로직 ---
    const lastWeek = Date.now() - (7 * 24 * 60 * 60 * 1000);
    const recentArticles = articles.filter(a => a.timestamp >= lastWeek);
    
    let buyCount = 0;
    let sellCount = 0;
    let holdCount = 0;
    let targetPrices = [];

    recentArticles.forEach(a => {
      const t = a.title;
      // 주요 경제지/증권사 리포트 키워드 체크
      const majorProviders = ['뉴시스','한국경제','뉴스1','이데일리','연합뉴스','뉴스핌','서울경제','매일경제','머니투데이','파이낸셜뉴스','비즈워치'];
      const isMajor = majorProviders.some(p => a.provider.includes(p));
      
      if (isMajor || t.includes('리포트') || t.includes('목표')) {
        // 의견 분석 (제목 키워드 중심)
        if (t.includes('매수') || t.includes('상향') || t.includes('BUY')) buyCount++;
        else if (t.includes('매도') || t.includes('하향') || t.includes('SELL')) sellCount++;
        else if (t.includes('중립') || t.includes('보유') || t.includes('HOLD')) holdCount++;

        // 목표가 추출 (예: 100,000원, 10만원 등)
        const priceMatch = t.match(/(\d{1,3}(,\d{3})*|\d+)\s*(만원|원)/);
        if (priceMatch) {
          let priceStr = priceMatch[1].replace(/,/g, '');
          let priceNum = parseInt(priceStr);
          if (priceMatch[3] === '만원') priceNum *= 10000;
          if (priceNum > 500) targetPrices.push(priceNum); 
        }
      }
    });

    const avgPrice = targetPrices.length > 0 
      ? Math.round(targetPrices.reduce((a, b) => a + b, 0) / targetPrices.length) 
      : 0;

    return res.status(200).json({ 
      data: articles,
      summary: {
        total_reports: recentArticles.length,
        buy: buyCount,
        sell: sellCount,
        neutral: holdCount,
        avg_target: avgPrice,
        price_mentions: targetPrices.length
      }
    });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
};
