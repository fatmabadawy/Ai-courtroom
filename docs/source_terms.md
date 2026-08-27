# Public Legal Data Sources — Terms & Rate Limits

This document records the terms of use, licensing, and rate limits for public legal search providers integrated into Member E's search adapter (`backend/app/api/services/search_service.py`).

---

## 1. CourtListener (Free Law Project)

- **Provider**: Free Law Project (501(c)(3) non-profit).
- **API Endpoint**: `https://www.courtlistener.com/api/rest/v4/`
- **Data Provided**: Federal and state court opinions, dockets, oral arguments, RECAP archive.
- **Authentication**: Token-based authentication via `Authorization: Token <API_KEY>`.
- **Terms of Service**:
  - Open data, but bulk downloading or aggressive scraping is restricted to prevent server overload.
  - Data is public domain / CC-0 where applicable.
  - Attribution requested: "Data provided by Free Law Project / CourtListener".
- **Rate Limits**:
  - Authenticated: Up to 5,000 requests / hour standard.
  - Search endpoint (`/api/rest/v4/search/`): Max 10 requests per minute recommended for non-cached queries.
- **Integration Policy in AI Courtroom**:
  - Used as **primary source** for Mode B public case acquisition.
  - If no API key is provided or the endpoint returns empty/error, the search adapter falls back gracefully to GovInfo.

---

## 2. GovInfo API (U.S. Government Publishing Office)

- **Provider**: U.S. Government Publishing Office (GPO).
- **API Endpoint**: `https://api.govinfo.gov/`
- **Data Provided**: Congressional bills, hearings, public laws, Federal Register, U.S. Courts opinions (selected jurisdictions).
- **Authentication**: API key query parameter `api_key=<API_KEY>` or header `X-Api-Key`.
- **Terms of Service**:
  - U.S. Government Works (Public Domain, no copyright restriction within the United States).
  - Subject to GPO Website Terms and Conditions.
- **Rate Limits**:
  - Default rate limit: 1,000 requests / hour per API key.
- **Integration Policy in AI Courtroom**:
  - Used as **secondary fallback** when CourtListener yields no matches or is unavailable.

---

## 3. Fallback / "No Data" Behavior

- If neither provider yields results matching the user's query or no API keys are configured:
  - The API MUST return `{"insufficient_public_data": true, "results": []}`.
  - Under NO circumstances does the system fabricate or hallucinate fake legal precedents or court citations.
