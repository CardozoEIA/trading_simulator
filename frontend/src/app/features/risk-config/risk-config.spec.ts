import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RiskConfig } from './risk-config';

describe('RiskConfig', () => {
  let component: RiskConfig;
  let fixture: ComponentFixture<RiskConfig>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RiskConfig]
    })
    .compileComponents();

    fixture = TestBed.createComponent(RiskConfig);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
