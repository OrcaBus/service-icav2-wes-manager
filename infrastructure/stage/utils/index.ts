export function camelCaseToSnakeCase(camelCase: string): string {
  return camelCase.replace(/([A-Z])/g, '_$1').toLowerCase();
}
