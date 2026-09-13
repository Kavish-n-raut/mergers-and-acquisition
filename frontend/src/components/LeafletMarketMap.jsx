import React, { useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from "react-leaflet";

function ViewportWatcher({ onViewportChange }) {
  const map = useMapEvents({
    moveend: () => {
      const b = map.getBounds();
      onViewportChange({
        north: b.getNorth(),
        south: b.getSouth(),
        east: b.getEast(),
        west: b.getWest(),
      });
    },
  });
  useEffect(() => {
    // initial notify
    const b = map.getBounds();
    onViewportChange({ north: b.getNorth(), south: b.getSouth(), east: b.getEast(), west: b.getWest() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

export default function LeafletMarketMap({ locations = [], onViewportChange }) {
  const defaultCenter = [39.2, -96.5];
  const defaultZoom = 3;

  const markers = useMemo(() => locations || [], [locations]);

  return (
    <MapContainer center={defaultCenter} zoom={defaultZoom} style={{ width: "100%", height: "520px" }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
      <ViewportWatcher onViewportChange={onViewportChange} />
      {markers.map((m) => (
        <CircleMarker
          key={m.id}
          center={[m.latitude, m.longitude]}
          radius={7}
          pathOptions={{ color: "#31c6a0", fillOpacity: 0.9 }}
        >
          <Popup>
            <div style={{ minWidth: 200 }}>
              <strong>{m.name}</strong>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                <div>{m.category}</div>
                {m.address && <div style={{ marginTop: 6 }}>{m.address}</div>}
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
