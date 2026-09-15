import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Asset } from '../models/asset.model';
import { Strategy } from '../models/strategy.model';
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

  public getStrategies(){
    return this.http.get<Strategy[]>(`${this.baseUrl}/backtest/strategies`)
  }

  public configureBacktest(asset: string, startDate: string, endDate: string, initialCapital: number, strategies: string[]){
    return this.http.post<BacktestConfigurationResponse>(`${this.baseUrl}/backtest/configuration`, {
      asset: asset,
      start_date: startDate,
      end_date: endDate,
      initial_capital: initialCapital,
      strategies: strategies
    })
  }
}