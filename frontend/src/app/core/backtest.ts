import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Asset } from '../models/asset.model';
import { BacktestConfigurationResponse } from '../models/backtest-configuration-response.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class Backtest {

  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl;

  public getAssets(){
    return this.http.get<Asset[]>(`${this.baseUrl}/backtest/assets`)
  }

  public configureBacktest(asset: string, startDate: string, endDate: string){
    return this.http.post<BacktestConfigurationResponse>(`${this.baseUrl}/backtest/configuration`, { asset: asset, start_date: startDate, end_date: endDate })
  }
}
