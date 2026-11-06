import { Pipe, PipeTransform } from '@angular/core';
import { BranchRef } from './auth.models';
import { BranchGroup, branchGroups } from './branch-options';

/** Groups branches under the warehouse that supplies them, for a mat-select with mat-optgroup. */
@Pipe({ name: 'branchGroups' })
export class BranchGroupsPipe implements PipeTransform {
  transform(branches: readonly BranchRef[] | null | undefined): BranchGroup[] {
    return branchGroups(branches ?? []);
  }
}
