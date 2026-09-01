import { inject, Injectable } from '@angular/core';
import { RiskConfiguration } from '../models/risk-configuration.model';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { RiskConfigurationResponse } from '../models/risk-configuration-response.model';

@Injectable({
  providedIn: 'root',
})
export class Risk {

  private http = inject(HttpClient)
  private baseUrl = environment.apiUrl

  public configureRisk(configuration: RiskConfiguration) {
    return this.http.post<RiskConfigurationResponse>(`${this.baseUrl}/risk/configuration`, configuration )
  }
}
