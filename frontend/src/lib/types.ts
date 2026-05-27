export interface Identificacion {
  cliente_vendedor: string | null;
  mandante: string | null;
  representante_legal: string | null;
  fecha_subasta: string | null;
  numero_lote: number | null;
  propiedad: string | null;
  comuna: string | null;
  fecha_firma_mandato: string | null;
}

export interface Insumos {
  adjudicacion_pesos: number | null;
  adjudicacion_uf: number | null;
  uf_dia_subasta: number | null;
  adjudicacion_uf_en_pesos: number | null;
  precio_proyectado_uf: number | null;
  abonos_comprador_pesos: number | null;
}

export interface TramoAplicado {
  tipo_propiedad: string | null;
  base_uf: number;
  base_uf_efectiva?: number;
  base_pesos: number | null;
  porcentaje: number;
  condicion: string;
}

export interface Parametros {
  tipo_comision: string;
  paga_premio: boolean;
  tramo_aplicado: TramoAplicado | null;
  tipo_propiedad: string | null;
  condicion_premio: string | null;
  paga_publicidad: boolean;
}

export interface Calculo {
  comision: number | null;
  comision_macal: number | null;
  iva_comision: number;
  premio: number;
  iva_premio: number;
  publicidad: number;
  iva_publicidad: number;
  vale_vista_var: string | null;
  costo_vale_vista: number;
  monto_vale_vista: number;
  instrucciones_var: string | null;
  costo_instrucciones: number;
  descuenta_gastos: string | null;
  antecedentes_var: string | null;
  costo_antecedentes: number;
  deducciones_totales: number;
  total_gastos: number;
  liquidacion_vendedor_teorica: number | null;
  saldo_por_pagar_al_vendedor: number | null;
}

export interface ResultadoLiquidacion {
  identificacion: Identificacion;
  insumos: Insumos;
  parametros: Parametros;
  calculo: Calculo;
  alertas: string[];
}

export interface FormData {
  vale_vista: "Sí" | "No" | "";
  costo_vale_vista: string;
  monto_vale_vista: string;
  instrucciones: "Sí" | "No" | "";
  costo_instrucciones: string;
  antecedentes: "Sí" | "No" | "";
  costo_antecedentes: string;
  descuenta_gastos: "Sí" | "No" | "";
}
