import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Backtest } from './backtest';

describe('Backtest.configureBacktest (US-21, US-24)', () => {
  let service: Backtest;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(Backtest);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('sends built-in codes and custom strategy ids separately, with the ensemble threshold', () => {
    service
      .configureBacktest('SP500', '2020-01-01', '2020-12-31', 10000, ['RSI', 'CUSTOM:abc-123', 'SMA'], 0.2)
      .subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/backtest/configuration'));
    expect(request.request.body).toEqual({
      asset: 'SP500',
      start_date: '2020-01-01',
      end_date: '2020-12-31',
      initial_capital: 10000,
      strategies: ['RSI', 'SMA'],
      custom_strategy_ids: ['abc-123'],
      ensemble_threshold: 0.2,
    });
    request.flush({});
  });

  it('leaves the threshold empty by default', () => {
    service.configureBacktest('SP500', '2020-01-01', '2020-12-31', 5000, ['RSI']).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/backtest/configuration'));
    expect(request.request.body.ensemble_threshold).toBeNull();
    expect(request.request.body.custom_strategy_ids).toEqual([]);
    request.flush({});
  });
});
