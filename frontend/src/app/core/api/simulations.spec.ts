import { TestBed } from '@angular/core/testing';

import { Simulations } from './simulations';

describe('Simulations', () => {
  let service: Simulations;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Simulations);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
