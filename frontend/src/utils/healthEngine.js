const MAX_HEALTH_SCORE = 100


const HEALTH_LEVELS = {
  excellent: {
    label: 'ممتاز',
    englishLabel: 'Excellent',
    tone: 'excellent',
    risk: 'منخفض جدًا',
  },

  good: {
    label: 'جيد',
    englishLabel: 'Good',
    tone: 'good',
    risk: 'منخفض',
  },

  warning: {
    label: 'تحذير',
    englishLabel: 'Warning',
    tone: 'warning',
    risk: 'متوسط',
  },

  critical: {
    label: 'حرج',
    englishLabel: 'Critical',
    tone: 'critical',
    risk: 'مرتفع',
  },
}


const SECTION_MAXIMUMS = {
  connectivity: 20,
  cpu: 20,
  memory: 15,
  interfaces: 20,
  errors: 15,
  utilization: 10,
}


const SEVERITY_PRIORITY = {
  critical: 5,
  warning: 4,
  notice: 3,
  info: 2,
  healthy: 1,
}


function clamp(
  value,
  minimum = 0,
  maximum = 100,
) {
  return Math.max(
    minimum,
    Math.min(
      Number(value) || 0,
      maximum,
    ),
  )
}


function normalizeNumber(
  value,
  fallback = 0,
) {
  const numericValue = Number(value)

  return Number.isFinite(
    numericValue,
  )
    ? numericValue
    : fallback
}


function createFinding({
  id,
  severity = 'info',
  category,
  title,
  description,
  recommendation = '',
  interfaceName = null,
  evidence = null,
}) {
  return {
    id,
    severity,
    category,
    title,
    description,
    recommendation,

    interface_name:
      interfaceName,

    evidence,
  }
}


function createDeduction({
  id,
  section,
  points,
  severity,
  title,
  description,
  interfaceName = null,
}) {
  const normalizedPoints =
    Math.max(
      0,
      Number(points) || 0,
    )

  return {
    id,
    section,
    points: normalizedPoints,
    severity,
    title,
    description,

    interface_name:
      interfaceName,
  }
}


function evaluateConnectivity({
  isOnline,
  interfaces,
}) {
  const maximum =
    SECTION_MAXIMUMS.connectivity

  if (!isOnline) {
    return {
      score: 0,

      findings: [
        createFinding({
          id: 'device-offline',
          severity: 'critical',
          category: 'connectivity',
          title: 'الجهاز غير متصل',
          description:
            'تعذر الوصول إلى الجهاز أو لا توجد استجابة من نظام المراقبة.',
          recommendation:
            'تحقق من الطاقة والاتصال والمسار وSNMP وMikroTik API.',
        }),
      ],

      deductions: [
        createDeduction({
          id: 'connectivity-device-offline',
          section: 'connectivity',
          points: maximum,
          severity: 'critical',
          title:
            'الجهاز غير متصل',
          description:
            'تم خصم جميع نقاط الاتصال لعدم توفر استجابة من الجهاز.',
        }),
      ],
    }
  }

  const upInterfaces =
    interfaces.filter(
      (item) =>
        item.is_oper_up,
    ).length

  if (
    interfaces.length > 0 &&
    upInterfaces === 0
  ) {
    return {
      score: 8,

      findings: [
        createFinding({
          id: 'all-interfaces-down',
          severity: 'critical',
          category: 'connectivity',
          title:
            'جميع الواجهات متوقفة',
          description:
            'الجهاز متصل، ولكن لا توجد واجهة تشغيلية.',
          recommendation:
            'تحقق من الكوابل والطرف المقابل وPoE وحالة الرابط.',
        }),
      ],

      deductions: [
        createDeduction({
          id: 'connectivity-no-operational-interface',
          section: 'connectivity',
          points: 12,
          severity: 'critical',
          title:
            'لا توجد واجهة تشغيلية',
          description:
            'الجهاز يستجيب، لكن جميع الواجهات في حالة توقف.',
        }),
      ],
    }
  }

  return {
    score: maximum,

    findings: [
      createFinding({
        id: 'device-online',
        severity: 'healthy',
        category: 'connectivity',
        title:
          'الجهاز متصل ويستجيب',
        description:
          `${upInterfaces} واجهة تعمل من أصل ${interfaces.length}.`,
      }),
    ],

    deductions: [],
  }
}


function evaluateCpu(
  cpuUsage,
) {
  const maximum =
    SECTION_MAXIMUMS.cpu

  const value =
    normalizeNumber(
      cpuUsage,
      0,
    )

  if (value >= 95) {
    return {
      score: 0,

      findings: [
        createFinding({
          id: 'cpu-critical',
          severity: 'critical',
          category: 'cpu',
          title:
            'استخدام المعالج في مستوى حرج',
          description:
            `وصل استخدام CPU إلى ${value}%.`,
          recommendation:
            'تحقق من الاتصالات النشطة وConnection Tracking وFirewall وQueues.',
          evidence: {
            cpu_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'cpu-critical-deduction',
          section: 'cpu',
          points: maximum,
          severity: 'critical',
          title:
            'استخدام CPU حرج',
          description:
            `تم خصم ${maximum} نقطة بسبب وصول CPU إلى ${value}%.`,
        }),
      ],
    }
  }

  if (value >= 85) {
    return {
      score: 6,

      findings: [
        createFinding({
          id: 'cpu-high',
          severity: 'warning',
          category: 'cpu',
          title:
            'ارتفاع استخدام المعالج',
          description:
            `استخدام CPU الحالي ${value}%.`,
          recommendation:
            'راقب الحمل وافحص Firewall وQueues والارتفاعات المفاجئة في الحركة.',
          evidence: {
            cpu_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'cpu-high-deduction',
          section: 'cpu',
          points: 14,
          severity: 'warning',
          title:
            'استخدام CPU مرتفع',
          description:
            `تم خصم 14 نقطة بسبب وصول CPU إلى ${value}%.`,
        }),
      ],
    }
  }

  if (value >= 70) {
    return {
      score: 13,

      findings: [
        createFinding({
          id: 'cpu-elevated',
          severity: 'notice',
          category: 'cpu',
          title:
            'استخدام المعالج مرتفع نسبيًا',
          description:
            `استخدام CPU الحالي ${value}%.`,
          recommendation:
            'لا يوجد إجراء عاجل، لكن يوصى بمتابعة اتجاه الحمل.',
          evidence: {
            cpu_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'cpu-elevated-deduction',
          section: 'cpu',
          points: 7,
          severity: 'notice',
          title:
            'استخدام CPU أعلى من المستوى المفضل',
          description:
            `تم خصم 7 نقاط لأن CPU بلغ ${value}%.`,
        }),
      ],
    }
  }

  return {
    score: maximum,

    findings: [
      createFinding({
        id: 'cpu-healthy',
        severity: 'healthy',
        category: 'cpu',
        title:
          'استخدام المعالج طبيعي',
        description:
          `استخدام CPU الحالي ${value}%.`,
        evidence: {
          cpu_usage: value,
        },
      }),
    ],

    deductions: [],
  }
}


function evaluateMemory(
  memoryUsage,
) {
  const maximum =
    SECTION_MAXIMUMS.memory

  const value =
    normalizeNumber(
      memoryUsage,
      0,
    )

  if (value >= 95) {
    return {
      score: 0,

      findings: [
        createFinding({
          id: 'memory-critical',
          severity: 'critical',
          category: 'memory',
          title:
            'استخدام الذاكرة في مستوى حرج',
          description:
            `وصل استخدام الذاكرة إلى ${value}%.`,
          recommendation:
            'افحص عدد الاتصالات والخدمات النشطة والذاكرة الحرة.',
          evidence: {
            memory_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'memory-critical-deduction',
          section: 'memory',
          points: maximum,
          severity: 'critical',
          title:
            'استخدام الذاكرة حرج',
          description:
            `تم خصم ${maximum} نقطة بسبب وصول الذاكرة إلى ${value}%.`,
        }),
      ],
    }
  }

  if (value >= 85) {
    return {
      score: 5,

      findings: [
        createFinding({
          id: 'memory-high',
          severity: 'warning',
          category: 'memory',
          title:
            'استخدام الذاكرة مرتفع',
          description:
            `استخدام الذاكرة الحالي ${value}%.`,
          recommendation:
            'راقب الذاكرة الحرة وعدد الاتصالات والخدمات النشطة.',
          evidence: {
            memory_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'memory-high-deduction',
          section: 'memory',
          points: 10,
          severity: 'warning',
          title:
            'استخدام الذاكرة مرتفع',
          description:
            `تم خصم 10 نقاط بسبب وصول الذاكرة إلى ${value}%.`,
        }),
      ],
    }
  }

  if (value >= 75) {
    return {
      score: 10,

      findings: [
        createFinding({
          id: 'memory-elevated',
          severity: 'notice',
          category: 'memory',
          title:
            'استخدام الذاكرة مرتفع نسبيًا',
          description:
            `استخدام الذاكرة الحالي ${value}%.`,
          recommendation:
            'لا يوجد إجراء عاجل، لكن يوصى بمتابعة الاتجاه.',
          evidence: {
            memory_usage: value,
          },
        }),
      ],

      deductions: [
        createDeduction({
          id: 'memory-elevated-deduction',
          section: 'memory',
          points: 5,
          severity: 'notice',
          title:
            'استخدام الذاكرة أعلى من المستوى المفضل',
          description:
            `تم خصم 5 نقاط لأن استخدام الذاكرة بلغ ${value}%.`,
        }),
      ],
    }
  }

  return {
    score: maximum,

    findings: [
      createFinding({
        id: 'memory-healthy',
        severity: 'healthy',
        category: 'memory',
        title:
          'استخدام الذاكرة طبيعي',
        description:
          `استخدام الذاكرة الحالي ${value}%.`,
        evidence: {
          memory_usage: value,
        },
      }),
    ],

    deductions: [],
  }
}


function evaluateInterfaces(
  interfaces,
) {
  const maximum =
    SECTION_MAXIMUMS.interfaces

  if (!interfaces.length) {
    return {
      score: 8,

      findings: [
        createFinding({
          id: 'interfaces-unavailable',
          severity: 'warning',
          category: 'interfaces',
          title:
            'بيانات الواجهات غير متوفرة',
          description:
            'لم يتم استلام بيانات كافية لتقييم واجهات الجهاز.',
          recommendation:
            'تحقق من SNMP وTelegraf وInfluxDB.',
        }),
      ],

      deductions: [
        createDeduction({
          id: 'interfaces-data-unavailable',
          section: 'interfaces',
          points: 12,
          severity: 'warning',
          title:
            'بيانات الواجهات غير متوفرة',
          description:
            'تم خصم 12 نقطة لعدم توفر بيانات كافية عن الواجهات.',
        }),
      ],
    }
  }

  const adminUpOperDown =
    interfaces.filter(
      (item) =>
        item.is_admin_up &&
        !item.is_oper_up,
    )

  const administrativelyDown =
    interfaces.filter(
      (item) =>
        !item.is_admin_up,
    )

  const findings = []
  const deductions = []

  let score = maximum

  if (adminUpOperDown.length) {
    const deduction =
      adminUpOperDown.length >= 5
        ? 10
        : Math.min(
            8,
            adminUpOperDown.length * 2,
          )

    score -= deduction

    findings.push(
      createFinding({
        id: 'interfaces-oper-down',
        severity:
          adminUpOperDown.length >= 5
            ? 'warning'
            : 'notice',
        category: 'interfaces',
        title:
          'واجهات مفعلة إداريًا لكنها متوقفة تشغيليًا',
        description:
          `${adminUpOperDown.length} واجهة في حالة Admin Up / Oper Down.`,
        recommendation:
          'تحقق من الكابل والطرف المقابل وPoE وSFP وحالة الرابط.',
        evidence: {
          interfaces:
            adminUpOperDown.map(
              (item) =>
                item.if_descr,
            ),
        },
      }),
    )

    deductions.push(
      createDeduction({
        id: 'interfaces-oper-down-deduction',
        section: 'interfaces',
        points: deduction,
        severity:
          adminUpOperDown.length >= 5
            ? 'warning'
            : 'notice',
        title:
          'واجهات تشغيلية متوقفة',
        description:
          `تم خصم ${deduction} نقاط بسبب وجود ${adminUpOperDown.length} واجهة Admin Up / Oper Down.`,
      }),
    )
  }

  if (
    administrativelyDown.length
  ) {
    findings.push(
      createFinding({
        id: 'interfaces-admin-down',
        severity: 'info',
        category: 'interfaces',
        title:
          'واجهات معطلة إداريًا',
        description:
          `${administrativelyDown.length} واجهة معطلة إداريًا.`,
        recommendation:
          'لا يلزم إجراء إذا كان التعطيل مقصودًا.',
        evidence: {
          interfaces:
            administrativelyDown.map(
              (item) =>
                item.if_descr,
            ),
        },
      }),
    )
  }

  if (!findings.length) {
    findings.push(
      createFinding({
        id: 'interfaces-healthy',
        severity: 'healthy',
        category: 'interfaces',
        title:
          'حالة الواجهات مستقرة',
        description:
          'لا توجد مشاكل تشغيلية ظاهرة في الواجهات.',
      }),
    )
  }

  return {
    score: clamp(
      score,
      0,
      maximum,
    ),

    findings,
    deductions,
  }
}


function evaluateErrors(
  interfaces,
) {
  const maximum =
    SECTION_MAXIMUMS.errors

  const interfacesWithErrors =
    interfaces.filter(
      (item) =>
        item.has_errors ||
        normalizeNumber(
          item.total_errors,
          normalizeNumber(
            item.rx_errors,
          ) +
            normalizeNumber(
              item.tx_errors,
            ),
        ) > 0,
    )

  if (!interfacesWithErrors.length) {
    return {
      score: maximum,

      findings: [
        createFinding({
          id: 'errors-none',
          severity: 'healthy',
          category: 'errors',
          title:
            'لا توجد أخطاء منافذ',
          description:
            'لم يتم اكتشاف RX/TX Errors في الواجهات.',
        }),
      ],

      deductions: [],
    }
  }

  const totalErrors =
    interfacesWithErrors.reduce(
      (sum, item) =>
        sum +
        normalizeNumber(
          item.total_errors,
          normalizeNumber(
            item.rx_errors,
          ) +
            normalizeNumber(
              item.tx_errors,
            ),
        ),
      0,
    )

  const score =
    totalErrors >= 100
      ? 0
      : totalErrors >= 20
        ? 5
        : totalErrors >= 5
          ? 9
          : 12

  const deduction =
    maximum - score

  const findings =
    interfacesWithErrors.map(
      (item) => {
        const total =
          normalizeNumber(
            item.total_errors,
            normalizeNumber(
              item.rx_errors,
            ) +
              normalizeNumber(
                item.tx_errors,
              ),
          )

        return createFinding({
          id:
            `errors-${item.if_descr}`,
          severity:
            total >= 20
              ? 'critical'
              : 'warning',
          category: 'errors',
          title:
            `أخطاء على ${item.if_descr}`,
          description:
            `RX Errors: ${item.rx_errors || 0} — TX Errors: ${item.tx_errors || 0}.`,
          recommendation:
            'تحقق من جودة الرابط والكابل وDuplex وMTU والطرف المقابل.',
          interfaceName:
            item.if_descr,
          evidence: {
            rx_errors:
              item.rx_errors || 0,
            tx_errors:
              item.tx_errors || 0,
            total_errors: total,
          },
        })
      },
    )

  return {
    score,
    findings,

    deductions: [
      createDeduction({
        id: 'interface-errors-deduction',
        section: 'errors',
        points: deduction,
        severity:
          totalErrors >= 20
            ? 'critical'
            : 'warning',
        title:
          'تم اكتشاف أخطاء منافذ',
        description:
          `تم خصم ${deduction} نقاط بسبب وجود ${totalErrors} خطأ على ${interfacesWithErrors.length} واجهة.`,
        interfaceName:
          interfacesWithErrors[0]
            ?.if_descr || null,
      }),
    ],
  }
}


function evaluateUtilization(
  interfaces,
) {
  const maximum =
    SECTION_MAXIMUMS.utilization

  const measurable =
    interfaces.filter(
      (item) =>
        item.utilization_percent !==
          null &&
        item.utilization_percent !==
          undefined,
    )

  if (!measurable.length) {
    return {
      score: 7,

      findings: [
        createFinding({
          id: 'utilization-unavailable',
          severity: 'info',
          category: 'utilization',
          title:
            'نسبة الاستخدام غير متوفرة',
          description:
            'بعض الواجهات لا تحتوي على Link Speed يمكن استخدامه للحساب.',
          recommendation:
            'إضافة ifHighSpeed ستحسن دقة الحساب للواجهات السريعة والافتراضية.',
        }),
      ],

      deductions: [
        createDeduction({
          id: 'utilization-unavailable-deduction',
          section: 'utilization',
          points: 3,
          severity: 'info',
          title:
            'بيانات استخدام غير مكتملة',
          description:
            'تم خصم 3 نقاط بسبب عدم توفر Link Speed لبعض الواجهات.',
        }),
      ],
    }
  }

  const critical =
    measurable.filter(
      (item) =>
        item.utilization_percent >=
        90,
    )

  if (critical.length) {
    return {
      score: 0,

      findings:
        critical.map((item) =>
          createFinding({
            id:
              `utilization-critical-${item.if_descr}`,
            severity: 'critical',
            category: 'utilization',
            title:
              `ازدحام حرج على ${item.if_descr}`,
            description:
              `وصل الاستخدام إلى ${item.utilization_percent.toFixed(2)}%.`,
            recommendation:
              'تحقق من Top Talkers وQueues وارفع السعة أو وزع الحركة.',
            interfaceName:
              item.if_descr,
            evidence: {
              utilization_percent:
                item.utilization_percent,
            },
          }),
        ),

      deductions: [
        createDeduction({
          id: 'utilization-critical-deduction',
          section: 'utilization',
          points: maximum,
          severity: 'critical',
          title:
            'ازدحام حرج',
          description:
            `تم خصم ${maximum} نقاط بسبب تجاوز الاستخدام 90%.`,
          interfaceName:
            critical[0]?.if_descr ||
            null,
        }),
      ],
    }
  }

  const warning =
    measurable.filter(
      (item) =>
        item.utilization_percent >=
          75 &&
        item.utilization_percent <
          90,
    )

  if (warning.length) {
    return {
      score: 5,

      findings:
        warning.map((item) =>
          createFinding({
            id:
              `utilization-warning-${item.if_descr}`,
            severity: 'warning',
            category: 'utilization',
            title:
              `استخدام مرتفع على ${item.if_descr}`,
            description:
              `وصل الاستخدام إلى ${item.utilization_percent.toFixed(2)}%.`,
            recommendation:
              'راقب ساعات الذروة وافحص توزيع الحركة.',
            interfaceName:
              item.if_descr,
            evidence: {
              utilization_percent:
                item.utilization_percent,
            },
          }),
        ),

      deductions: [
        createDeduction({
          id: 'utilization-warning-deduction',
          section: 'utilization',
          points: 5,
          severity: 'warning',
          title:
            'استخدام مرتفع',
          description:
            'تم خصم 5 نقاط بسبب تجاوز استخدام إحدى الواجهات 75%.',
          interfaceName:
            warning[0]?.if_descr ||
            null,
        }),
      ],
    }
  }

  const highest =
    [...measurable].sort(
      (first, second) =>
        second.utilization_percent -
        first.utilization_percent,
    )[0]

  return {
    score: maximum,

    findings: [
      createFinding({
        id: 'utilization-healthy',
        severity: 'healthy',
        category: 'utilization',
        title:
          'استخدام الواجهات ضمن الحدود الطبيعية',
        description:
          highest
            ? `أعلى استخدام حالي ${highest.utilization_percent.toFixed(2)}% على ${highest.if_descr}.`
            : 'لا يوجد استخدام مرتفع.',
      }),
    ],

    deductions: [],
  }
}


function resolveHealthLevel(
  score,
) {
  if (score >= 90) {
    return HEALTH_LEVELS.excellent
  }

  if (score >= 75) {
    return HEALTH_LEVELS.good
  }

  if (score >= 60) {
    return HEALTH_LEVELS.warning
  }

  return HEALTH_LEVELS.critical
}


function buildPrimaryRecommendation(
  findings,
) {
  const highestPriorityFinding =
    [...findings]
      .filter(
        (item) =>
          item.recommendation,
      )
      .sort(
        (first, second) =>
          (
            SEVERITY_PRIORITY[
              second.severity
            ] || 0
          ) -
          (
            SEVERITY_PRIORITY[
              first.severity
            ] || 0
          ),
      )[0]

  if (
    highestPriorityFinding
  ) {
    return {
      title:
        highestPriorityFinding.title,

      recommendation:
        highestPriorityFinding.recommendation,

      severity:
        highestPriorityFinding.severity,

      interface_name:
        highestPriorityFinding.interface_name,
    }
  }

  return {
    title:
      'لا توجد إجراءات عاجلة',

    recommendation:
      'استمر في المراقبة الدورية، ولا توجد توصية تصحيحية حالية.',

    severity: 'healthy',
    interface_name: null,
  }
}


function resolveTopRisk(
  deductions,
) {
  if (!deductions.length) {
    return {
      title:
        'لا توجد مخاطر مؤثرة',
      description:
        'لم يتم اكتشاف خصومات على درجة الصحة.',
      severity: 'healthy',
      points: 0,
      section: null,
      interface_name: null,
    }
  }

  const sorted =
    [...deductions].sort(
      (first, second) => {
        const pointsDifference =
          second.points -
          first.points

        if (pointsDifference !== 0) {
          return pointsDifference
        }

        return (
          SEVERITY_PRIORITY[
            second.severity
          ] || 0
        ) -
          (
            SEVERITY_PRIORITY[
              first.severity
            ] || 0
          )
      },
    )

  return sorted[0]
}


export function calculateDeviceHealth({
  isOnline,
  cpuUsage,
  memoryUsage,
  interfaces = [],
} = {}) {
  const safeInterfaces =
    Array.isArray(interfaces)
      ? interfaces
      : []

  const connectivityResult =
    evaluateConnectivity({
      isOnline,
      interfaces: safeInterfaces,
    })

  const cpuResult =
    evaluateCpu(cpuUsage)

  const memoryResult =
    evaluateMemory(memoryUsage)

  const interfacesResult =
    evaluateInterfaces(
      safeInterfaces,
    )

  const errorsResult =
    evaluateErrors(
      safeInterfaces,
    )

  const utilizationResult =
    evaluateUtilization(
      safeInterfaces,
    )

  const sections = {
    connectivity:
      connectivityResult.score,

    cpu:
      cpuResult.score,

    memory:
      memoryResult.score,

    interfaces:
      interfacesResult.score,

    errors:
      errorsResult.score,

    utilization:
      utilizationResult.score,
  }

  const score =
    clamp(
      Object.values(
        sections,
      ).reduce(
        (sum, value) =>
          sum +
          normalizeNumber(value),
        0,
      ),
    )

  const findings = [
    ...connectivityResult.findings,
    ...cpuResult.findings,
    ...memoryResult.findings,
    ...interfacesResult.findings,
    ...errorsResult.findings,
    ...utilizationResult.findings,
  ].filter(Boolean)

  const deductions = [
    ...connectivityResult.deductions,
    ...cpuResult.deductions,
    ...memoryResult.deductions,
    ...interfacesResult.deductions,
    ...errorsResult.deductions,
    ...utilizationResult.deductions,
  ]
    .filter(
      (item) =>
        item &&
        item.points > 0,
    )
    .sort(
      (first, second) =>
        second.points -
        first.points,
    )

  const totalDeduction =
    deductions.reduce(
      (sum, item) =>
        sum + item.points,
      0,
    )

  const counters =
    findings.reduce(
      (result, item) => {
        if (
          item.severity ===
          'critical'
        ) {
          result.critical += 1
        } else if (
          item.severity ===
          'warning'
        ) {
          result.warning += 1
        } else if (
          item.severity ===
          'notice'
        ) {
          result.notice += 1
        } else if (
          item.severity ===
          'healthy'
        ) {
          result.healthy += 1
        } else {
          result.info += 1
        }

        return result
      },
      {
        critical: 0,
        warning: 0,
        notice: 0,
        info: 0,
        healthy: 0,
      },
    )

  const level =
    resolveHealthLevel(score)

  const topRisk =
    resolveTopRisk(
      deductions,
    )

  return {
    score,
    maxScore:
      MAX_HEALTH_SCORE,

    totalDeduction,

    level,
    risk: level.risk,

    sections,
    sectionMaximums:
      SECTION_MAXIMUMS,

    findings,
    deductions,
    counters,
    topRisk,

    scoreExplanation: {
      baseScore:
        MAX_HEALTH_SCORE,

      finalScore:
        score,

      totalDeduction,

      deductionCount:
        deductions.length,

      message:
        deductions.length
          ? `بدأ التقييم من ${MAX_HEALTH_SCORE} نقطة، وتم خصم ${totalDeduction} نقطة بسبب ${deductions.length} عوامل تشغيلية.`
          : `الجهاز حصل على الدرجة الكاملة ${MAX_HEALTH_SCORE} دون خصومات تشغيلية.`,
    },

    primaryRecommendation:
      buildPrimaryRecommendation(
        findings,
      ),

    generatedAt:
      new Date().toISOString(),
  }
}


export {
  HEALTH_LEVELS,
  MAX_HEALTH_SCORE,
  SECTION_MAXIMUMS,
  SEVERITY_PRIORITY,
}
