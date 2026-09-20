import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { ConfigurationSummaryResponse } from '../models/configuration-summary-response.model';
import { SimulationResponse } from '../models/simulation-response.model';
import { Decision } from '../models/decision.model';
import { Trade } from '../models/trade.model';
import { EquityPoint } from '../models/equity-point.model';
import { Signal } from '../models/signal.model';


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
}