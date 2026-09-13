import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { getCompanyProfile, searchCompanyMap, getCompaniesBBox } from "../lib/api";
import { DEMO_DEAL, DEMO_RISKS, formatCurrency, getMarketIntelligence } from "../lib/dealUtils";
import LeafletMarketMap from "../components/LeafletMarketMap";

const tabs = [
  "Market Map",
  "Legal Entry Checklist",
  "Niche Analysis",
  "Competitors",
  "IPO/Public Company",
  "Market Entry Report",
];

const locationTypeLabels = {
  "Buyer HQ": "buyer",
  "Target HQ": "target",
  Competitor: "competitor",
  "Customer Market": "customer",
  "Regulatory Office": "regulatory",
  "Operating Region": "operating_region",
  "User Location": "user",
  "Manual Location": "manual",
};

const layerDefinitions = [
  { key: "buyer", label: "Buyer", roles: ["buyer"] },
  { key: "target", label: "Target", roles: ["target"] },
  { key: "competitor", label: "Competitors", roles: ["competitor"] },
  { key: "company", label: "Companies", roles: ["company"] },
  { key: "customer", label: "Customer Markets", roles: ["customer"] },
  { key: "regulatory", label: "Regulators", roles: ["regulatory"] },
  { key: "operating_region", label: "Operating Regions", roles: ["operating_region"] },
];

const defaultLayerVisibility = Object.fromEntries(layerDefinitions.map((layer) => [layer.key, true]));
const NOMINATIM_CACHE_KEY = "marketMapNominatimCache";
const NOMINATIM_LAST_REQUEST_KEY = "marketMapNominatimLastRequestAt";

export default function MarketIntelligencePage() {
  const [activeTab, setActiveTab] = useState("Market Map");
  const intelligence = getMarketIntelligence();
  const googleMapsKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "").trim();

  return (
    <div className="page market-intelligence-page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Market Entry Intelligence</p>
          <h2>Market Intelligence</h2>
          <p className="muted">Location, regulatory, competitor, and public-market context for the Aster Northstar entry thesis.</p>
        </div>
        <div className="source-stack">
          <span className="source-chip">{intelligence.dataMode}</span>
          <span className={`confidence-pill confidence-${intelligence.confidence.toLowerCase()}`}>Confidence: {intelligence.confidence}</span>
        </div>
      </section>

      <section className="workspace-summary market-summary">
        <div>
          <p className="eyebrow">Entry Thesis</p>
          <h3>{DEMO_DEAL.buyerName} entering {DEMO_DEAL.sector}</h3>
          <p className="muted">Buyer: {DEMO_DEAL.buyerName} | Target: {DEMO_DEAL.targetName} | Deal value: {formatCurrency(DEMO_DEAL.dealValue)}</p>
        </div>
        <div className="summary-side">
          <span className="source-chip">Updated {intelligence.generatedAt}</span>
          <span className="source-chip">Maps: Google Earth embed enabled</span>
        </div>
      </section>

      <div className="tab-bar market-tab-bar">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>{tab}</button>
        ))}
      </div>

      {activeTab === "Market Map" && <MarketMap intelligence={intelligence} googleMapsKey={googleMapsKey} />}
      {activeTab === "Legal Entry Checklist" && <LegalChecklist intelligence={intelligence} />}
      {activeTab === "Niche Analysis" && <NicheAnalysis intelligence={intelligence} />}
      {activeTab === "Competitors" && <CompetitorLandscape intelligence={intelligence} />}
      {activeTab === "IPO/Public Company" && <PublicCompanyIntelligence intelligence={intelligence} />}
      {activeTab === "Market Entry Report" && <MarketEntryReport intelligence={intelligence} />}
    </div>
  );
}

function MarketMap({ intelligence, googleMapsKey }) {
  const [provider, setProvider] = useState(() => (googleMapsKey ? "google" : "osm"));
  const [permissionStatus, setPermissionStatus] = useState("Not requested");
  const [userLocation, setUserLocation] = useState(null);
  const [manualPoint, setManualPoint] = useState(null);
  const [manualLocation, setManualLocation] = useState({ city: "", country: "" });
  const [layerVisibility, setLayerVisibility] = useState(defaultLayerVisibility);
  const [mapCommand, setMapCommand] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companyResponse, setCompanyResponse] = useState(null);
  const [companyError, setCompanyError] = useState("");
  const [loadingCompanies, setLoadingCompanies] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [profileError, setProfileError] = useState("");
  const [searchForm, setSearchForm] = useState({ q: "", country: "", sector: "", company_size: "", public_private: "", listed_exchange: "", mna_signal: "", distress_signal: "", ipo_public_company: "", marker_role: "" });
  const viewportRequestRef = useRef(null);
  const searchFormRef = useRef(searchForm);

  useEffect(() => {
    searchFormRef.current = searchForm;
  }, [searchForm]);

  const loadCompanies = async (overrides = {}) => {
    setLoadingCompanies(true);
    setCompanyError("");
    try {
      const params = Object.fromEntries(
        Object.entries({ ...searchForm, ...overrides, limit: 250 }).filter(([, value]) => value !== "" && value !== null && value !== undefined),
      );
      const data = await searchCompanyMap(params);
      setCompanyResponse(data);
      setCompanies(data.companies || []);
    } catch (error) {
      setCompanyError(error?.response?.data?.detail || error.message || "Unable to load company intelligence. Showing local fallback records.");
      setCompanies([]);
    } finally {
      setLoadingCompanies(false);
    }
  };

  useEffect(() => {
    loadCompanies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => {
    if (viewportRequestRef.current) window.clearTimeout(viewportRequestRef.current);
  }, []);

  const loadViewportCompanies = useCallback(async (bounds) => {
    if (!bounds) return;
    setLoadingCompanies(true);
    setCompanyError("");
    try {
        const params = Object.fromEntries(
          Object.entries({ ...searchFormRef.current, ...bounds, limit: 300 }).filter(([, value]) => value !== "" && value !== null && value !== undefined),
        );
        // Call Overpass-backed endpoint for viewport POIs
        const data = await getCompaniesBBox(params);
        // Map Overpass results into company-like objects used across the UI
        const mapped = (data.companies || []).map((c) => ({
          id: c.id,
          name: c.name,
          city: c.address || "",
          country: "",
          sector: c.category || "",
          company_size: "",
          public_private: "",
          listed_exchange: null,
          ticker: null,
          marker_role: c.category || "company",
          lat: c.lat ?? c.latitude,
          lng: c.lng ?? c.longitude,
          latitude: c.lat ?? c.latitude,
          longitude: c.lng ?? c.longitude,
          mna_signal: "Insufficient public data",
          confidence: "Low",
          signal_score: 0,
          signal_explanation: "Imported from OpenStreetMap via Overpass",
          data_source: "OpenStreetMap / Overpass",
          last_updated: new Date().toISOString(),
          source_mode: "live",
        }));
        setCompanyResponse({ companies: mapped, total: mapped.length, source_mode: "live" });
        setCompanies(mapped);
    } catch (error) {
      setCompanyError(error?.response?.data?.detail || error.message || "Viewport company loading failed. Try Search Companies or reset filters.");
    } finally {
      setLoadingCompanies(false);
    }
  }, []);

  const handleViewportChange = useCallback((bounds) => {
    if (viewportRequestRef.current) window.clearTimeout(viewportRequestRef.current);
    viewportRequestRef.current = window.setTimeout(() => loadViewportCompanies(bounds), 650);
  }, [loadViewportCompanies]);
  const activeCompanies = companies.length ? companies : [];
  const visibleBusinessLocations = useMemo(
    () => activeCompanies.filter((company) => layerVisibility[company.marker_role] !== false),
    [activeCompanies, layerVisibility],
  );

  const requestLocation = () => {
    if (!navigator.geolocation) {
      setPermissionStatus("Browser geolocation is not available. Use manual location entry.");
      return;
    }
    setPermissionStatus("Requesting browser permission...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setUserLocation({
          id: "user-location",
          name: "Your Location",
          type: "User Location",
          marker_role: "user",
          city: "Current browser location",
          country: "",
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          importance: "Approximate browser-provided location for route and proximity planning.",
          source: "Browser Geolocation API, user permission required",
          data_source: "Browser Geolocation API, user permission required",
          mna_signal: "Insufficient public data",
          confidence: "Insufficient public data",
        });
        setPermissionStatus("Permission granted. Your approximate location is available for route planning.");
      },
      () => setPermissionStatus("Permission denied. Use manual city and country entry below."),
      { enableHighAccuracy: false, timeout: 8000 },
    );
  };

  const resolveManualLocation = async () => {
    const query = [manualLocation.city, manualLocation.country].map((part) => part.trim()).filter(Boolean).join(", ");
    if (!query) {
      setPermissionStatus("Enter a city or country before resolving a manual location.");
      return;
    }

    setPermissionStatus("Searching OpenStreetMap / Nominatim...");
    try {
      const result = await geocodeWithNominatim(query);
      if (!result) {
        setManualPoint(null);
        setPermissionStatus(`No Nominatim result found for "${query}". Try a more specific city and country.`);
        return;
      }
      setManualPoint({
        id: `manual-${query.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
        name: query,
        type: "Manual Location",
        marker_role: "manual",
        city: manualLocation.city || result.display_name,
        country: manualLocation.country || "",
        lat: result.lat,
        lng: result.lng,
        importance: "Manual market-entry location entered by the user.",
        source: result.cached ? "Nominatim cache / OpenStreetMap" : "Nominatim / OpenStreetMap",
        data_source: result.cached ? "Nominatim cache / OpenStreetMap" : "Nominatim / OpenStreetMap",
        mna_signal: "Insufficient public data",
        confidence: "Insufficient public data",
      });
      setPermissionStatus(result.cached ? `Manual location loaded from cache: ${query}` : `Manual location resolved with Nominatim: ${query}`);
    } catch (error) {
      setManualPoint(null);
      setPermissionStatus(error.message || "Nominatim geocoding failed. Please retry later or use an existing map marker.");
    }
  };

  const toggleLayer = (key) => setLayerVisibility((current) => ({ ...current, [key]: !current[key] }));
  const activeProviderLabel = provider === "google" ? "Google Earth embed" : "OpenStreetMap / MapLibre enabled";
  const datasetLabel = sourceModeLabel(companyResponse?.source_mode);

  const openCompanyProfile = async (companyId) => {
    if (!companyId || companyId === "user-location" || companyId.startsWith("manual-")) return;
    setProfileError("");
    try {
      const data = await getCompanyProfile(companyId);
      setSelectedProfile(data);
    } catch (error) {
      setProfileError(error?.response?.data?.detail || "Unable to load company profile.");
    }
  };

  return (
    <section className="market-grid company-map-layout">
      <div className="panel-flat company-search-panel">
        <div className="section-title"><p className="eyebrow">Company Search</p><h3>Search & Filters</h3></div>
        <div className="form-stack">
          <input value={searchForm.q} onChange={(event) => setSearchForm({ ...searchForm, q: event.target.value })} placeholder="Company, city, sector, ticker, LEI" />
          <div className="form-grid compact">
            <input value={searchForm.country} onChange={(event) => setSearchForm({ ...searchForm, country: event.target.value })} placeholder="Country" />
            <input value={searchForm.sector} onChange={(event) => setSearchForm({ ...searchForm, sector: event.target.value })} placeholder="Sector" />
            <input value={searchForm.company_size} onChange={(event) => setSearchForm({ ...searchForm, company_size: event.target.value })} placeholder="Company size" />
            <select value={searchForm.public_private} onChange={(event) => setSearchForm({ ...searchForm, public_private: event.target.value })}><option value="">Public/private</option><option>Public</option><option>Private</option><option>Unknown</option></select>
            <input value={searchForm.listed_exchange} onChange={(event) => setSearchForm({ ...searchForm, listed_exchange: event.target.value })} placeholder="Exchange" />
            <select value={searchForm.mna_signal} onChange={(event) => setSearchForm({ ...searchForm, mna_signal: event.target.value })}><option value="">M&A signal</option><option>High</option><option>Medium</option><option>Low</option><option>Insufficient public data</option></select>
            <select value={searchForm.distress_signal} onChange={(event) => setSearchForm({ ...searchForm, distress_signal: event.target.value })}><option value="">Distress signal</option><option>High</option><option>Medium</option><option>Low</option><option>Insufficient public data</option></select>
            <select value={searchForm.ipo_public_company} onChange={(event) => setSearchForm({ ...searchForm, ipo_public_company: event.target.value })}><option value="">IPO/public company</option><option value="true">Public / IPO data</option><option value="false">Private or unknown</option></select>
            <select value={searchForm.marker_role} onChange={(event) => setSearchForm({ ...searchForm, marker_role: event.target.value })}><option value="">Role</option><option value="buyer">Buyer</option><option value="target">Target</option><option value="competitor">Competitor</option><option value="company">Company</option></select>
          </div>
          <div className="action-row">
            <button onClick={() => loadCompanies()}>Search Companies</button>
            <button className="secondary-button" onClick={() => { setSearchForm({ q: "", country: "", sector: "", company_size: "", public_private: "", listed_exchange: "", mna_signal: "", distress_signal: "", ipo_public_company: "", marker_role: "" }); loadCompanies({ q: "", country: "", sector: "", company_size: "", public_private: "", listed_exchange: "", mna_signal: "", distress_signal: "", ipo_public_company: "", marker_role: "" }); }}>Reset Filters</button>
          </div>
          <p className="muted">{loadingCompanies ? "Loading company intelligence..." : `${visibleBusinessLocations.length} companies visible. ${companyResponse?.note || "No company is marked as for sale without public evidence."}`}</p>
          {companyError && <p className="error-text">{companyError}</p>}
          {companyResponse && <span className={`source-chip source-mode-${companyResponse.source_mode}`}>{datasetLabel}</span>}
        </div>
      </div>

      <div className="panel-flat map-panel company-map-panel">
        <div className="section-title chart-title-row">
          <div><p className="eyebrow">Company Intelligence Map</p><h3>Public Company and Registry Signals</h3></div>
          <div className="source-stack">
            <span className="source-chip">{activeProviderLabel}</span>
            <span className={`source-chip source-mode-${companyResponse?.source_mode || "sample"}`}>{datasetLabel}</span>
          </div>
        </div>
        <p className="muted">Click a cluster to zoom in. At closer zoom levels, individual company markers appear with source-labeled popups and company profile links.</p>
        <p className="callout-text">M&A Signal is an evidence and confidence indicator only. No company is marked as open for sale unless direct public evidence is present.</p>
        <div className="map-provider-switch" aria-label="Map provider selector">
          <button className={provider === "osm" ? "active" : ""} onClick={() => setProvider("osm")}>OpenStreetMap</button>
          <button className={provider === "google" ? "active" : ""} onClick={() => setProvider("google")}>Google Earth</button>
        </div>
        {provider === "google" ? (
          <GoogleEarthEmbedMap apiKey={googleMapsKey} locations={visibleBusinessLocations} userLocation={userLocation} manualPoint={manualPoint} />
        ) : (
          <LeafletMarketMap
            locations={visibleBusinessLocations}
            userLocation={userLocation}
            manualPoint={manualPoint}
            mapCommand={mapCommand}
            onCompanySelect={openCompanyProfile}
            onViewportChange={handleViewportChange}
          />
        )}
        <MapLegend />
        <div className="map-source-notes">
          <span>Map data: OpenStreetMap</span>
          <span>Geocoding: Nominatim</span>
          <span>Company data: SEC EDGAR / GLEIF / registry-ready adapters / local fallback</span>
          <span>Map data © OpenStreetMap contributors</span>
          <span>Do not use this as legal/regulatory advice.</span>
        </div>
      </div>

      <VisibleCompanyPanel
        companies={visibleBusinessLocations}
        companyResponse={companyResponse}
        loading={loadingCompanies}
        error={companyError}
        onOpen={openCompanyProfile}
      />

      <div className="panel-flat map-controls-panel">
        <div className="section-title"><p className="eyebrow">Map Controls</p><h3>Location Tools</h3></div>
        <div className="action-grid map-action-grid">
          <button onClick={() => setMapCommand({ type: "fit", id: Date.now() })}>Fit to All Markers</button>
          <button className="secondary-button" onClick={requestLocation}>Use My Location</button>
          <button className="secondary-button" onClick={() => setMapCommand({ type: "reset", id: Date.now() })}>Reset Map</button>
        </div>
        <p className="callout-text">{permissionStatus}</p>
        <div className="form-grid compact">
          <label>Manual city<input value={manualLocation.city} onChange={(event) => setManualLocation({ ...manualLocation, city: event.target.value })} placeholder="Toronto" /></label>
          <label>Country<input value={manualLocation.country} onChange={(event) => setManualLocation({ ...manualLocation, country: event.target.value })} placeholder="Canada" /></label>
        </div>
        <button className="secondary-button" onClick={resolveManualLocation}>Search with Nominatim</button>
        <div className="section-title layer-title"><p className="eyebrow">Toggle Layers</p><h3>Visible Marker Groups</h3></div>
        <div className="layer-toggle-grid">
          {layerDefinitions.map((layer) => (
            <label key={layer.key} className="layer-toggle">
              <input type="checkbox" checked={layerVisibility[layer.key]} onChange={() => toggleLayer(layer.key)} />
              <span><i className={`legend-dot marker-${layer.key}`} />{layer.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="panel-flat span-3">
        <div className="section-title chart-title-row">
          <div><p className="eyebrow">Company Register</p><h3>Visible Intelligence Records</h3></div>
          <span className={`source-chip source-mode-${companyResponse?.source_mode || "sample"}`}>{datasetLabel}</span>
        </div>
        <CompanyDataState loading={loadingCompanies} error={companyError} companies={visibleBusinessLocations} />
        {!loadingCompanies && !companyError && visibleBusinessLocations.length > 0 && (
          <div className="company-result-grid">
            {visibleBusinessLocations.slice(0, 18).map((company) => <CompanyResultCard key={company.id} company={company} onOpen={() => openCompanyProfile(company.id)} />)}
          </div>
        )}
      </div>

      {selectedProfile && <CompanyProfileDrawer profile={selectedProfile} onClose={() => setSelectedProfile(null)} />}
      {profileError && <p className="error-text span-3">{profileError}</p>}
    </section>
  );
}
function MapLegend() {
  const entries = [
    ["Buyer HQ", "buyer"],
    ["Target HQ", "target"],
    ["Competitor", "competitor"],
    ["Company", "company"],
    ["Customer Market", "customer"],
    ["Regulatory Office", "regulatory"],
    ["Operating Region", "operating_region"],
    ["User Location", "user"],
    ["Manual Search", "manual"],
  ];
  return (
    <div className="map-legend" aria-label="Map marker legend">
      {entries.map(([label, type]) => (
        <span key={type}><i className={`legend-dot marker-${type}`} />{label}</span>
      ))}
    </div>
  );
}

function VisibleCompanyPanel({ companies, companyResponse, loading, error, onOpen }) {
  const datasetLabel = sourceModeLabel(companyResponse?.source_mode);

  return (
    <aside className="panel-flat visible-company-panel">
      <div className="section-title chart-title-row">
        <div>
          <p className="eyebrow">Companies in View</p>
          <h3>Current Map Area</h3>
        </div>
        <span className={`source-chip source-mode-${companyResponse?.source_mode || "sample"}`}>{datasetLabel}</span>
      </div>
      <CompanyDataState loading={loading} error={error} companies={companies} compact />
      {!loading && !error && companies.length > 0 && (
        <div className="visible-company-list">
          {companies.slice(0, 14).map((company) => (
            <button key={company.id} className="visible-company-row" onClick={() => onOpen(company.id)}>
              <span className={`legend-dot marker-${company.marker_role || "company"}`} />
              <strong>{company.name}</strong>
              <small>{company.city}, {company.country}</small>
              <em>{company.mna_signal} signal · {company.confidence}</em>
              <CompanySourceBadge company={company} />
            </button>
          ))}
        </div>
      )}
      {!loading && !error && companies.length > 14 && (
        <p className="subtext">Showing first 14 visible records. Use search or zoom to narrow the map.</p>
      )}
    </aside>
  );
}

function CompanyDataState({ loading, error, companies, compact = false }) {
  if (loading) {
    return <p className={`loading-state ${compact ? "compact-state" : ""}`}>Loading company intelligence for the current map area...</p>;
  }
  if (error) {
    return <p className={`error-text ${compact ? "compact-state" : ""}`}>{error}</p>;
  }
  if (!companies.length) {
    return <p className={`empty-state ${compact ? "compact-state" : ""}`}>No companies match the current map area and filters. Reset filters or zoom out to broaden the search.</p>;
  }
  return null;
}

function CompanySourceBadge({ company }) {
  return <small className={`source-badge source-mode-${company.source_mode}`}>{company.source_mode === "live" ? "Real public data" : "Sample data"}</small>;
}

function sourceModeLabel(mode = "sample") {
  if (mode === "live") return "Real public data";
  if (mode === "mixed") return "Public + sample data";
  if (mode === "cache") return "Cached public data";
  return "Sample company dataset";
}

async function geocodeWithNominatim(query) {
  const normalized = query.toLowerCase().trim();
  const cache = readJsonStorage(NOMINATIM_CACHE_KEY, {});
  if (cache[normalized]) return { ...cache[normalized], cached: true };

  const lastRequestAt = Number(localStorage.getItem(NOMINATIM_LAST_REQUEST_KEY) || 0);
  const elapsed = Date.now() - lastRequestAt;
  if (elapsed < 1100) await wait(1100 - elapsed);

  const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
  localStorage.setItem(NOMINATIM_LAST_REQUEST_KEY, String(Date.now()));
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Nominatim geocoding is unavailable right now. Please try again later.");
  const rows = await response.json();
  if (!rows?.length) return null;

  const first = rows[0];
  const result = {
    lat: Number(first.lat),
    lng: Number(first.lon),
    display_name: first.display_name,
  };
  if (!Number.isFinite(result.lat) || !Number.isFinite(result.lng)) return null;

  localStorage.setItem(NOMINATIM_CACHE_KEY, JSON.stringify({ ...cache, [normalized]: result }));
  return { ...result, cached: false };
}

function readJsonStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) || fallback;
  } catch {
    return fallback;
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function MapLibreMarketMap({ locations, userLocation, manualPoint, mapCommand, onCompanySelect, onViewportChange }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const didInitialFitRef = useRef(false);
  const [status, setStatus] = useState("Loading OpenStreetMap map...");
  const mapPoints = useMemo(
    () => [...locations, ...(userLocation ? [userLocation] : []), ...(manualPoint ? [manualPoint] : [])],
    [locations, manualPoint, userLocation],
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "Map data © OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm-raster", type: "raster", source: "osm" }],
      },
      center: [-96.5, 39.2],
      zoom: 3.25,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: "Map data © OpenStreetMap contributors" }), "bottom-right");
    map.on("load", () => {
      map.addSource("company-intelligence", {
        type: "geojson",
        data: buildCompanyGeoJson(mapPoints),
        cluster: true,
        clusterMaxZoom: 5,
        clusterRadius: 34,
      });
      map.addLayer({
        id: "company-clusters",
        type: "circle",
        source: "company-intelligence",
        filter: ["has", "point_count"],
        paint: {
          "circle-color": ["step", ["get", "point_count"], "#31c6a0", 10, "#d6a13a", 30, "#ef626c"],
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 24, 30, 32],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "company-cluster-count",
        type: "symbol",
        source: "company-intelligence",
        filter: ["has", "point_count"],
        layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12 },
        paint: { "text-color": "#07100d" },
      });
      map.addLayer({
        id: "company-points",
        type: "circle",
        source: "company-intelligence",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "match",
            ["get", "role"],
            "buyer", "#d6a13a",
            "target", "#31c6a0",
            "competitor", "#ef626c",
            "customer", "#6aa7ff",
            "regulatory", "#c68cff",
            "operating_region", "#f3b64b",
            "user", "#51c878",
            "manual", "#f8f1df",
            "#a7b2b8",
          ],
          "circle-radius": 9,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "company-point-labels",
        type: "symbol",
        source: "company-intelligence",
        filter: ["!", ["has", "point_count"]],
        layout: {
          "text-field": ["get", "short_name"],
          "text-size": 11,
          "text-offset": [0, 1.35],
          "text-anchor": "top",
        },
        paint: {
          "text-color": "#f8f1df",
          "text-halo-color": "#07100d",
          "text-halo-width": 1.4,
        },
      });
      map.on("click", "company-clusters", (event) => {
        const feature = map.queryRenderedFeatures(event.point, { layers: ["company-clusters"] })[0];
        const clusterId = feature?.properties?.cluster_id;
        const source = map.getSource("company-intelligence");
        const center = feature?.geometry?.coordinates;
        if (clusterId === undefined || !center || !source?.getClusterExpansionZoom) return;
        const zoomIntoCluster = (zoom) => {
          map.easeTo({ center, zoom: Math.max(zoom, map.getZoom() + 1.8), duration: 650 });
        };
        try {
          const maybeZoom = source.getClusterExpansionZoom(clusterId, (error, zoom) => {
            if (!error && Number.isFinite(zoom)) zoomIntoCluster(zoom);
          });
          if (typeof maybeZoom === "number") zoomIntoCluster(maybeZoom);
          if (maybeZoom?.then) maybeZoom.then((zoom) => zoomIntoCluster(zoom)).catch(() => zoomIntoCluster(map.getZoom() + 2));
        } catch {
          zoomIntoCluster(map.getZoom() + 2);
        }
      });
      map.on("click", "company-points", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;
        const properties = feature.properties || {};
        new maplibregl.Popup({ offset: 18, maxWidth: "300px" })
          .setLngLat(feature.geometry.coordinates)
          .setHTML(popupHtml(properties))
          .addTo(map);
        if (properties.id) onCompanySelect?.(properties.id);
      });
      ["company-clusters", "company-points"].forEach((layer) => {
        map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
      });
      const notifyViewport = () => {
        const bounds = map.getBounds();
        onViewportChange?.({
          north: bounds.getNorth(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          west: bounds.getWest(),
        });
      };
      map.on("moveend", notifyViewport);
      window.setTimeout(notifyViewport, 0);
      setStatus("OpenStreetMap map loaded with clustered company markers.");
      // Ensure map correctly sizes itself when the container was initially hidden
      // (common when rendered inside tabs or hidden panels). A short timeout
      // lets layout settle before forcing a resize.
      window.setTimeout(() => map.resize(), 0);
    });
    map.on("error", () => setStatus("Map tiles are temporarily unavailable. Check network access or retry."));
    mapRef.current = map;

    // Resize observer: ensure map redraws when container size changes
    const ro = new ResizeObserver(() => {
      try { map.resize(); } catch (e) { /* ignore */ }
    });
    ro.observe(containerRef.current);

    // Window resize fallback
    const onWinResize = () => { try { map.resize(); } catch (e) { } };
    window.addEventListener("resize", onWinResize);

    // If the document becomes visible again, force a resize (fixes hidden-tab mounts)
    const onVisibility = () => { if (document.visibilityState === "visible") { try { map.resize(); } catch (e) { } } };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", onWinResize);
      document.removeEventListener("visibilitychange", onVisibility);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const updateSource = () => map.getSource("company-intelligence")?.setData(buildCompanyGeoJson(mapPoints));
    if (map.isStyleLoaded()) updateSource();
    else map.once("load", updateSource);
    if (mapPoints.length && !didInitialFitRef.current) {
      fitMapToPoints(map, mapPoints, false);
      didInitialFitRef.current = true;
    }
    setStatus(`OpenStreetMap map showing ${mapPoints.length} active company markers with clustering.`);
  }, [mapPoints]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapCommand) return;
    if (mapCommand.type === "fit") fitMapToPoints(map, mapPoints, true);
    if (mapCommand.type === "reset") map.flyTo({ center: [-96.5, 39.2], zoom: 3.25, speed: 0.9 });
  }, [mapCommand, mapPoints]);

  return (
    <>
      <div ref={containerRef} className="maplibre-map" role="region" aria-label="OpenStreetMap market entry map" />
      <p className="muted">{status}</p>
    </>
  );
}

function buildCompanyGeoJson(points) {
  return {
    type: "FeatureCollection",
    features: points
      .filter((point) => Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lng)))
      .map((point) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [Number(point.lng), Number(point.lat)] },
        properties: {
          ...point,
          role: point.marker_role || locationTypeLabels[point.type] || "company",
          label: markerLabel(point.marker_role || point.type),
          short_name: shortCompanyName(point.name),
          city_country: [point.city, point.country].filter(Boolean).join(", "),
        },
      })),
  };
}

function shortCompanyName(name = "") {
  return String(name)
    .replace(/\b(Inc\.?|Corporation|Corp\.?|Company|Co\.?|Limited|Ltd\.?|PLC|AG|SE|LLC)\b/gi, "")
    .replace(/[,.]/g, "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .join(" ") || "Company";
}

function fitMapToPoints(map, points, animate = true) {
  const validPoints = points.filter((point) => Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lng)));
  if (!validPoints.length) return;
  const bounds = new maplibregl.LngLatBounds();
  validPoints.forEach((point) => bounds.extend([Number(point.lng), Number(point.lat)]));
  map.fitBounds(bounds, { padding: 70, maxZoom: 7.5, duration: animate ? 650 : 0 });
}

function GoogleEarthEmbedMap({ apiKey, locations, userLocation, manualPoint }) {
  const [status, setStatus] = useState("Loading Google Earth embed...");
  const mapPoints = useMemo(
    () => [...locations, ...(userLocation ? [userLocation] : []), ...(manualPoint ? [manualPoint] : [])],
    [locations, manualPoint, userLocation],
  );

  const shouldShowEmbed = Boolean(apiKey?.trim());
  const earthUrl = useMemo(() => {
    const centerPoint = mapPoints.find((point) => Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lng))) || { lat: 39.5, lng: -98.35 };
    const lat = Number(centerPoint.lat);
    const lng = Number(centerPoint.lng);
    return `https://www.google.com/maps/embed/v1/view?key=${encodeURIComponent(apiKey)}&center=${lat},${lng}&zoom=5&maptype=satellite`;
  }, [apiKey, mapPoints]);

  useEffect(() => {
    if (!shouldShowEmbed) {
      setStatus("Google Maps API key not configured. Switch to OpenStreetMap for local preview.");
      return;
    }
    setStatus(`Google Earth-style embed ready for ${mapPoints.length} locations.`);
  }, [mapPoints.length, shouldShowEmbed]);

  if (!shouldShowEmbed) {
    return (
      <>
        <div className="map-error-panel">
          <p className="error-text">Google Maps API key is not configured. Set <code>VITE_GOOGLE_MAPS_API_KEY</code> in <code>frontend/.env</code> to enable the Google Earth embed.</p>
          <MapLibreMarketMap locations={locations} userLocation={userLocation} manualPoint={manualPoint} mapCommand={null} />
        </div>
      </>
    );
  }

  return (
    <>
      <iframe
        title="Google Earth embed"
        src={earthUrl}
        className="google-map-frame"
        loading="eager"
        allowFullScreen
        referrerPolicy="no-referrer-when-downgrade"
        onLoad={() => setStatus(`Google Earth-style embed ready for ${mapPoints.length} locations.`)}
        onError={() => setStatus("Google Earth embed could not be loaded. Please try again or switch to OpenStreetMap.")}
      />
      <p className="muted">{status}</p>
    </>
  );
}

function markerLabel(type) {
  const labels = {
    buyer: "B",
    target: "T",
    competitor: "C",
    customer: "M",
    regulatory: "R",
    operating_region: "O",
    company: "Co",
    user: "U",
    manual: "S",
    "Buyer HQ": "B",
    "Target HQ": "T",
    Competitor: "C",
    "Customer Market": "M",
    "Regulatory Office": "R",
    "Operating Region": "O",
    "User Location": "U",
    "Manual Location": "S",
  };
  return labels[type] || "L";
}

function popupHtml(point) {
  const cityCountry = point.city_country || [point.city, point.country].filter(Boolean).join(", ") || "Location details unavailable";
  return `
    <div class="deal-map-popup">
      <strong>${escapeHtml(point.name)}</strong>
      <span>${escapeHtml(markerRoleTitle(point.marker_role || point.role || point.type || "company"))}</span>
      <p><b>Location:</b> ${escapeHtml(cityCountry)}</p>
      <p><b>Sector:</b> ${escapeHtml(point.sector || "Insufficient public data")}</p>
      <p><b>M&A Signal:</b> ${escapeHtml(point.mna_signal || "Insufficient public data")} · ${escapeHtml(point.confidence || "Insufficient public data")}</p>
      <small>${point.source_mode === "live" ? "Real public data" : "Sample company dataset"}</small>
      <small>Source: ${escapeHtml(point.data_source || point.source || "Local demo data")}</small>
      <button type="button">View Company Profile</button>
    </div>
  `;
}

function markerRoleTitle(role) {
  return String(role || "company")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function CompanyResultCard({ company, onOpen }) {
  return (
    <article className="company-result-card">
      <div className="checklist-card-header">
        <h4>{company.name}</h4>
        <span className={`confidence-pill confidence-${confidenceClass(company.confidence)}`}>{company.confidence}</span>
      </div>
      <p className="muted">{company.headquarters || `${company.city}, ${company.country}`}</p>
      <div className="info-list compact-info-list">
        <div><span>Sector</span><strong>{company.sector}</strong></div>
        <div><span>Status</span><strong>{company.public_private}{company.ticker ? ` / ${company.ticker}` : ""}</strong></div>
        <div><span>M&A Signal</span><strong>{company.mna_signal}</strong></div>
        <div><span>Source</span><strong>{company.source_mode === "live" ? "Real public data" : "Sample data"}</strong></div>
      </div>
      <p>{company.signal_explanation}</p>
      <p className="subtext">Source: {company.data_source}. Last updated: {company.last_updated}</p>
      <button className="secondary-button small-button" onClick={onOpen}>View Company Profile</button>
    </article>
  );
}

function CompanyProfileDrawer({ profile, onClose }) {
  const company = profile.company;
  return (
    <aside className="drawer company-profile-drawer">
      <button className="drawer-close" onClick={onClose}>Close</button>
      <p className="eyebrow">Company Profile</p>
      <h3>{company.name}</h3>
      <span className={`confidence-pill confidence-${confidenceClass(company.confidence)}`}>M&A Signal: {company.mna_signal}</span>
      <div className="detail-grid">
        <div><span>Headquarters</span><strong>{company.headquarters}</strong></div>
        <div><span>Country</span><strong>{company.country}</strong></div>
        <div><span>Sector</span><strong>{company.sector}</strong></div>
        <div><span>Public/private</span><strong>{company.public_private}</strong></div>
        <div><span>Ticker</span><strong>{company.ticker || "Not available"}</strong></div>
        <div><span>Estimated size</span><strong>{company.company_size}</strong></div>
      </div>
      <section>
        <h4>Overview</h4>
        <p>{profile.overview}</p>
      </section>
      <section>
        <h4>M&A Signal Explanation</h4>
        <p>{profile.mna_signal_explanation}</p>
      </section>
      <section>
        <h4>Filings / Registry Links</h4>
        <ul className="clean-list">
          {profile.filings_registry_links.length ? profile.filings_registry_links.map((link) => <li key={link.url}><a href={link.url} target="_blank" rel="noreferrer">{link.label}</a></li>) : <li>Insufficient public registry links in local mode.</li>}
        </ul>
      </section>
      <section>
        <h4>Competitors Nearby</h4>
        <ul className="clean-list">
          {profile.competitors_nearby.map((item) => <li key={item.id}>{item.name} - {item.city}, {item.country}</li>)}
        </ul>
      </section>
      <section>
        <h4>Legal / Regulatory Notes</h4>
        <ul className="clean-list">
          {profile.legal_regulatory_notes.map((note) => <li key={note}>{note}</li>)}
        </ul>
      </section>
      <section>
        <h4>IPO / Public Company Details</h4>
        <pre className="document-preview">{JSON.stringify(profile.ipo_public_company_details, null, 2)}</pre>
      </section>
      <p className="subtext">Data source: {company.data_source}. Last updated: {company.last_updated}</p>
    </aside>
  );
}

function confidenceClass(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "high") return "high";
  if (normalized === "medium") return "medium";
  return "low";
}

function LocationCard({ location }) {
  const className = locationTypeLabels[location.type] || "region";
  return (
    <article className={`location-card location-${className}`}>
      <span className="source-chip">{location.type}</span>
      <h4>{location.name}</h4>
      <p>{location.city}, {location.country}</p>
      <p className="muted">{location.importance}</p>
      <p className="subtext">Source: {location.source || "Local demo data"}</p>
    </article>
  );
}

function LegalChecklist({ intelligence }) {
  const [context, setContext] = useState(intelligence.entryContext);
  const [generated, setGenerated] = useState(true);

  return (
    <section className="market-grid">
      <div className="panel-flat span-3 legal-disclaimer">
        <strong>This is workflow guidance, not legal advice. Local counsel review required.</strong>
        <p className="muted">The checklist below is jurisdiction-aware workflow guidance for deal teams. It should be validated by qualified local counsel before any transaction decision.</p>
      </div>

      <div className="panel-flat span-3">
        <div className="section-title"><p className="eyebrow">Entry Inputs</p><h3>Jurisdiction and Deal Context</h3></div>
        <div className="form-grid">
          <ContextField label="Buyer country" value={context.buyerCountry} onChange={(value) => setContext({ ...context, buyerCountry: value })} />
          <ContextField label="Target country" value={context.targetCountry} onChange={(value) => setContext({ ...context, targetCountry: value })} />
          <ContextField label="Market entry country" value={context.marketEntryCountry} onChange={(value) => setContext({ ...context, marketEntryCountry: value })} />
          <ContextField label="Employee countries" value={context.employeeCountries} onChange={(value) => setContext({ ...context, employeeCountries: value })} />
          <ContextField label="Data hosting countries" value={context.dataHostingCountries} onChange={(value) => setContext({ ...context, dataHostingCountries: value })} />
          <ContextField label="Sector" value={context.sector} onChange={(value) => setContext({ ...context, sector: value })} />
          <label>Deal type<select value={context.dealType} onChange={(event) => setContext({ ...context, dealType: event.target.value })}><option>Acquisition</option><option>Merger</option><option>Minority Investment</option><option>Carve-Out</option></select></label>
        </div>
        <button onClick={() => setGenerated(true)}>Generate Checklist</button>
      </div>

      {generated && (
        <div className="panel-flat span-3">
          <div className="section-title chart-title-row">
            <div><p className="eyebrow">Legal and Regulatory Checklist</p><h3>{context.marketEntryCountry} Market Entry Readiness</h3></div>
            <span className="source-chip">Sample workflow guidance</span>
          </div>
          <div className="checklist-grid">
            {intelligence.legalChecklist.map((item) => (
              <article key={item.area} className="checklist-card">
                <div className="checklist-card-header"><h4>{item.area}</h4><span className={`term-status status-${item.status.toLowerCase().replace(/\s+/g, "_")}`}>{item.status}</span></div>
                <p>{item.guidance}</p>
                <p className="muted"><strong>Owner:</strong> {item.owner}</p>
                <p className="muted"><strong>Mitigation:</strong> {item.mitigation}</p>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function ContextField({ label, value, onChange }) {
  return <label>{label}<input value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function NicheAnalysis({ intelligence }) {
  const niche = intelligence.nicheAnalysis;
  return (
    <section className="market-grid">
      <div className="panel-flat span-2">
        <div className="section-title"><p className="eyebrow">Market Niche</p><h3>{niche.niche}</h3></div>
        <div className="detail-grid">
          <div><span>Target Customer Segment</span><strong>{niche.customerSegment}</strong></div>
          <div><span>Market Size Estimate</span><strong>{niche.marketSizeEstimate}</strong></div>
        </div>
        <div className="recommendation"><strong>Why the acquisition helps:</strong> {niche.acquisitionRationale}</div>
      </div>
      <ListPanel title="Growth Drivers" items={niche.growthDrivers} eyebrow="Demand Signals" />
      <ListPanel title="Key Pain Points" items={niche.painPoints} eyebrow="Customer Need" />
      <div className="panel-flat span-2">
        <div className="section-title"><p className="eyebrow">Barriers to Entry</p><h3>Market Access Constraints</h3></div>
        <div className="barrier-grid">
          <Barrier title="Regulatory Barriers" text={niche.barriers.regulatory} />
          <Barrier title="Technology Barriers" text={niche.barriers.technology} />
          <Barrier title="Distribution Barriers" text={niche.barriers.distribution} />
        </div>
      </div>
    </section>
  );
}

function ListPanel({ eyebrow, title, items }) {
  return (
    <div className="panel-flat">
      <div className="section-title"><p className="eyebrow">{eyebrow}</p><h3>{title}</h3></div>
      <ul className="clean-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </div>
  );
}

function Barrier({ title, text }) {
  return <article className="barrier-card"><h4>{title}</h4><p>{text}</p></article>;
}

function CompetitorLandscape({ intelligence }) {
  return (
    <section className="market-grid">
      <div className="panel-flat span-3">
        <div className="section-title chart-title-row">
          <div><p className="eyebrow">Competitive Landscape</p><h3>Likely Market Response</h3></div>
          <span className="source-chip">Sample unless public source is configured</span>
        </div>
        <div className="competitor-grid">
          {intelligence.competitors.map((competitor) => (
            <article key={competitor.name} className="competitor-card">
              <div className="checklist-card-header"><h4>{competitor.name}</h4><span className="source-chip">{competitor.confidence}</span></div>
              <p className="muted">{competitor.headquarters}</p>
              <div className="competitor-detail"><span>Business model</span><strong>{competitor.businessModel}</strong></div>
              <div className="competitor-detail"><span>Estimated market position</span><strong>{competitor.marketPosition}</strong></div>
              <div className="competitor-columns">
                <p><strong>Strengths:</strong> {competitor.strengths}</p>
                <p><strong>Weaknesses:</strong> {competitor.weaknesses}</p>
              </div>
              <div className="recommendation"><strong>Likely response:</strong> {competitor.likelyResponse}</div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function PublicCompanyIntelligence({ intelligence }) {
  return (
    <section className="market-grid">
      <div className="panel-flat span-3">
        <div className="section-title chart-title-row">
          <div><p className="eyebrow">IPO and Public Company Intelligence</p><h3>Market Data Availability</h3></div>
          <span className="source-chip">SEC EDGAR / Stooq ready</span>
        </div>
        <p className="muted">No real-time public-company facts are fabricated. If a ticker is not configured or public data is unavailable, the field is explicitly marked as not applicable or insufficient public data.</p>
        <div className="public-company-grid">
          {intelligence.publicCompanyIntelligence.map((company) => <PublicCompanyCard key={company.company} company={company} />)}
        </div>
      </div>
    </section>
  );
}

function PublicCompanyCard({ company }) {
  const rows = [
    ["Ticker", company.ticker],
    ["Exchange", company.exchange],
    ["IPO date", company.ipoDate],
    ["IPO price", company.ipoPrice],
    ["Current market cap", company.currentMarketCap],
    ["Revenue", company.revenue],
    ["EBITDA / net income", company.ebitdaOrNetIncome],
    ["Share price trend", company.sharePriceTrend],
    ["SEC / filing links", company.secLinks],
    ["Latest annual report", company.annualReport],
    ["Latest quarterly report", company.quarterlyReport],
    ["Major shareholders", company.majorShareholders],
    ["Lock-up expiry", company.lockupExpiry],
    ["Analyst / market sentiment", company.sentiment],
  ];
  return (
    <article className="public-company-card">
      <div className="checklist-card-header"><h4>{company.company}</h4><span className="source-chip">{company.publicStatus}</span></div>
      <div className="info-list">
        {rows.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      <p className="muted"><strong>Source:</strong> {company.source}</p>
    </article>
  );
}

function MarketEntryReport({ intelligence }) {
  return (
    <section className="market-grid">
      <div className="panel-flat span-3">
        <div className="section-title chart-title-row">
          <div><p className="eyebrow">Market Entry Report</p><h3>Board-Ready Briefing Outline</h3></div>
          <button>Download Market Entry Report</button>
        </div>
        <div className="report-section-grid">
          {intelligence.reportSections.map((section, index) => (
            <article key={section.title} className="report-section-card">
              <span className="source-chip">Section {index + 1}</span>
              <h4>{section.title}</h4>
              <p>{section.body}</p>
            </article>
          ))}
        </div>
      </div>
      <div className="panel-flat span-3">
        <div className="section-title"><p className="eyebrow">Risk Carryover</p><h3>Market Entry Risks from Diligence</h3></div>
        <div className="risk-grid">
          {DEMO_RISKS.slice(0, 3).map((risk) => (
            <article key={risk.risk_category} className={`risk-card severity-${risk.severity.toLowerCase()}`}>
              <span className="severity-badge">{risk.severity}</span>
              <h3>{risk.risk_category}</h3>
              <p>{risk.ai_explanation}</p>
              <p className="muted"><strong>Recommended action:</strong> {risk.recommended_action}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}


