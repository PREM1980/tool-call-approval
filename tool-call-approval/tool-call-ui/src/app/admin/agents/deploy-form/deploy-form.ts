import { Component, EventEmitter, Output } from '@angular/core';
@Component({ selector: 'app-deploy-form', standalone: true, template: '<p>Deployments</p>' })
export class DeployForm {
  @Output() deployed = new EventEmitter<void>();
}
