/**
 * Vercel Serverless Function
 * 엔드포인트: GET /api/data?key=<SECRET_QUANT_API_KEY>
 * 성공 시 최신 kospi_top30_api.json 반환
 */

const GITHUB_RAW =
  'https://raw.githubusercontent.com/HGG142352/dailyticker/main/kospi_top30_api.json';

module.exports = async (req, res) => {
  // CORS 헤더
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Cache-Control', 'no-store');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // API 키 검증
  const clientKey = req.query.key || '';
  const validKey  = process.env.SECRET_QUANT_API_KEY || '';

  if (!validKey) {
    return res.status(500).json({ error: 'Server misconfiguration: API key not set.' });
  }

  if (clientKey !== validKey) {
    return res.status(401).json({ error: 'Unauthorized: invalid API key.' });
  }

  // GitHub Raw에서 최신 데이터 가져오기
  try {
    const upstream = await fetch(`${GITHUB_RAW}?t=${Date.now()}`);
    if (!upstream.ok) {
      return res.status(502).json({ error: `Upstream fetch failed: ${upstream.status}` });
    }
    const data = await upstream.json();
    return res.status(200).json(data);
  } catch (err) {
    return res.status(500).json({ error: `Internal error: ${err.message}` });
  }
};
