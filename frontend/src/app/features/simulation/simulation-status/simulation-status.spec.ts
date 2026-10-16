import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SimulationStatus } from './simulation-status';

describe('SimulationStatus', () => {
  let component: SimulationStatus;
  let fixture: ComponentFixture<SimulationStatus>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SimulationStatus]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SimulationStatus);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
