import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { ConfigurationSummaryResponse } from '@models/simulation/configuration-summary-response.model';
import { SimulationResponse } from '@models/simulation/simulation-response.model';
import { Decision } from '@models/analysis/decision.model';
import { Trade } from '@models/analysis/trade.model';
import { EquityPoint } from '@models/analysis/equity-point.model';
import { Signal } from '@models/analysis/signal.model';
import { SimulationMetrics } from '@models/analysis/metrics.model';
import { SimulationHistoryItem } from '@models/simulation/simulation-history.model';
import { SimulationInsights } from '@models/agent/insights.model';

@Injectable({
  providedIn: 'root',
})
export class Simulations {

  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  public getConfigurationSummary(configurationId: string) {
    return this.http.get<ConfigurationSummaryResponse>(`${this.baseUrl}/simulations/configuration/${configurationId}/summary`);
  }

  public startSimulation(configurationId: string) {
    return this.http.post<SimulationResponse>(`${this.baseUrl}/simulations/start`, { configuration_id: configurationId });
  }

  public getSimulationStatus(simulationId: string) {
    return this.http.get<SimulationResponse>(`${this.baseUrl}/simulations/${simulationId}/status`);
  }
  public getDecisions(simulationId: string) {
    return this.http.get<Decision[]>(`${this.baseUrl}/simulations/${simulationId}/decisions`);
  }

  public getTrades(simulationId: string) {
    return this.http.get<Trade[]>(`${this.baseUrl}/simulations/${simulationId}/trades`);
  }
  public getEquityCurve(simulationId: string) {
    return this.http.get<EquityPoint[]>(`${this.baseUrl}/simulations/${simulationId}/equity-curve`);
  }
  // agregar a core/simulations.ts
  public getSignals(simulationId: string) {
    return this.http.get<Signal[]>(`${this.baseUrl}/simulations/${simulationId}/signals`);
  }
  public explainDecision(simulationId: string, date: string) {
    return this.http.post<{ explanation: string }>(
      `${this.baseUrl}/simulations/${simulationId}/explain`,
      { date }
    );
  }
  public getMetrics(simulationId: string) {
    return this.http.get<SimulationMetrics>(`${this.baseUrl}/results/${simulationId}/metrics`);
  }
  public getHistory() {
    return this.http.get<SimulationHistoryItem[]>(`${this.baseUrl}/simulations/history`);
  }
  public getInsights(simulationId: string) {
    return this.http.get<SimulationInsights>(`${this.baseUrl}/simulations/${simulationId}/insights`);
  }
  public generateInsights(simulationId: string) {
    return this.http.post<SimulationInsights>(`${this.baseUrl}/simulations/${simulationId}/insights`, {});
  }
}
