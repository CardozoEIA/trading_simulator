import { ComponentFixture, TestBed } from '@angular/core/testing';

import { StepIndicator } from './step-indicator';

describe('StepIndicator', () => {
  let component: StepIndicator;
  let fixture: ComponentFixture<StepIndicator>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [StepIndicator]
    })
    .compileComponents();

    fixture = TestBed.createComponent(StepIndicator);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
