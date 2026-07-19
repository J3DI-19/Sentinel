import { useEffect, useState } from "react";
import { getSystemStatus, type ServiceStatus } from "./api/health";
import "./styles.css";

function displayStatus(service: ServiceStatus): string {
  if (service.service === "ollama") {
    if (!service.available) return "Offline (optional)";
    return service.model_installed ? "Online · model ready" : "Online · model not installed";
  }
  return service.status === "ok" ? "Ready" : "Unavailable";
}

export default function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);

  useEffect(() => {
    getSystemStatus().then(setServices);
  }, []);

  return (
    <main className="page">
      <h1>Sentinel</h1>
      <p>Step 1 initialization test page</p>
      <section aria-labelledby="status-heading">
        <h2 id="status-heading">Service status</h2>
        <div className="status-list">
          {services.map((service) => (
            <p className="status-item" key={service.service}>
              <span>{service.service}</span>
              <strong className={service.status === "ok" || service.available ? "ready" : "unavailable"}>
                {displayStatus(service)}
              </strong>
            </p>
          ))}
        </div>
      </section>
    </main>
  );
}
