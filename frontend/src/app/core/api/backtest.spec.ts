import { TestBed } from '@angular/core/testing';

import { Backtest } from './backtest';

describe('Backtest', () => {
  let service: Backtest;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Backtest);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
