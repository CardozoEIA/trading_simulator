import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SimulationConfig } from './simulation-config';

describe('SimulationConfig', () => {
  let component: SimulationConfig;
  let fixture: ComponentFixture<SimulationConfig>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SimulationConfig]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SimulationConfig);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
