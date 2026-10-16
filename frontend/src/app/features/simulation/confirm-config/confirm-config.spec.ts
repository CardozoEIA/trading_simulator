import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ConfirmConfig } from './confirm-config';

describe('ConfirmConfig', () => {
  let component: ConfirmConfig;
  let fixture: ComponentFixture<ConfirmConfig>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfirmConfig]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ConfirmConfig);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
