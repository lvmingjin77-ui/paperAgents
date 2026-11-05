# 虚构练习：从论文论证到可复用推理策略

**以下材料全部为虚构教学练习，不对应真实论文、作者、数据或实验。** 所有 ID 都带练习语义；不存在 DOI、发表记录或已完成的实验。例子的用途是演示当前产物 schema 与证据分类，禁止将其加入真实语料、专家知识库或实验结论。

示例讨论如何比较不同设备的残差异常程度。它不是新颖性声明，也不证明此方法有效。`step` 是论证组织次序，不是作者实际研究时间线。

## 虚构来源材料

<a id="s1"></a>
### S1：问题设定

我们考虑两个设备的异常检测。它们在正常状态下有不同的残差噪声尺度，因此同样大小的原始残差不一定表示同样罕见的事件。本文关心不同设备的正常误报率能否可比。

<a id="s2"></a>
### S2：作者明确指出的前提

若使用同一个原始残差阈值来控制误报率，就隐含要求各设备正常残差的尺度可比。我们质疑这一前提，而不把不同设备的误报率差异直接解释为预测器质量差异。

<a id="s3"></a>
### S3：作者明确提出的假设

令设备条件为可在预测时观测的 c，残差为 r。我们提出使用 z = |r| / sigma(c)，其中 sigma(c) 只从正常训练数据估计。假设正常残差属于共同形状的尺度族且尺度为正，条件标准化后的分布应更可比；这可能帮助统一阈值控制误报率，但不保证异常召回率提高。

<a id="s4"></a>
### S4：作者列出的实验计划

我们计划比较原始残差阈值与条件标准化阈值，分别考察正常噪声尺度相等及不等的条件，报告各条件误报率与异常召回率。本文练习材料未提供这些实验的执行结果。

<a id="s5"></a>
### S5：材料边界

本练习没有源码、训练记录或研究日志；未说明作者的灵感来源、尝试顺序或实际发现过程。

## 与当前 paper schema 兼容的产物

以下 JSON 是一份**仅用于结构校验的虚构产物**。此例对应当前论文契约，包含必需的 `paper_understanding`、论证图字段和 `reasoning_patterns`；`exercise_only` 与具体迁移展开是可选扩展。版本由 request/schema 选定，不新增产物版本字段。来源锚点指向本文件上方的虚构段落，不能当真实文献引用。

**模拟文件声明：** `EXERCISE_ONLY/not-a-real-paper.md` 不存在，全零 `sha256` 是测试占位值，不是文件摘要。`status: read` 和覆盖状态只是夹具中模拟的输入；通过本地结构与 ID 校验不代表这些材料真实存在，更不能通过正式运行的路径/摘要核验。不要将本夹具提交到研究流程。

```json
{
  "expert_id": "exercise-only-conditional-residual-expert",
  "paper_id": "fictional-conditional-residual-v1",
  "exercise_only": true,
  "knowledge": {
    "profile": {
      "title": "虚构练习：条件化残差比较",
      "scope": "只用于演示证据表达和产物结构，不代表实际领域能力",
      "source_status": "fictional_training_material"
    },
    "claims": [
      {
        "claim_id": "exercise-claim-formula",
        "statement": "虚构材料 S3 提出了 z = |r| / sigma(c)，并限制 sigma(c) 仅由正常训练数据估计。",
        "basis": "source_fact",
        "source_refs": [
          {
            "source_id": "exercise-source",
            "locator": "skills/references/idea-trace-example.md#s3",
            "source_kind": "fictional_exercise",
            "anchor_id": "s3"
          }
        ]
      },
      {
        "claim_id": "exercise-claim-representation",
        "statement": "系统将 S2 到 S3 的联系归纳为：先识别可比性前提，再把原始量转换为相对于条件尺度的量。材料未说作者以这个策略名称思考。",
        "basis": "system_inference",
        "source_refs": [
          {
            "source_id": "exercise-source",
            "locator": "skills/references/idea-trace-example.md#s2",
            "anchor_id": "s2"
          },
          {
            "source_id": "exercise-source",
            "locator": "skills/references/idea-trace-example.md#s3",
            "anchor_id": "s3"
          }
        ]
      }
    ],
    "reasoning_patterns": [
      {
        "pattern_id": "exercise-pattern-conditional-comparability",
        "basis": "system_inference",
        "trace_refs": [
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t2"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t3"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t5"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t6"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t7"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t10"
          },
          {
            "paper_id": "fictional-conditional-residual-v1",
            "trace_id": "t11"
          }
        ],
        "source_refs": [
          {
            "source_id": "exercise-source",
            "locator": "skills/references/idea-trace-example.md#s2",
            "anchor_id": "s2"
          },
          {
            "source_id": "exercise-source",
            "locator": "skills/references/idea-trace-example.md#s3",
            "anchor_id": "s3"
          }
        ],
        "trigger": "一个统一指标或阈值在不同条件下可能不具有相同含义。",
        "transfer_checks": [
          "在新任务中先确定条件变量与目标的关系，避免把有效信号当作干扰消除。",
          "按 t5 和 t6 区分尺度解释、额外调参解释以及有限样本误差。"
        ],
        "validation_status": "从虚构文字归纳；未实现、未执行、未验证迁移效果",
        "name": "检验混合总体的可比性，并尝试条件化表示",
        "problem_type": "统一阈值或指标混合了条件不同的总体，导致比较含义可能不一致。",
        "reasoning_move": "把原始量转换为相对于条件尺度的量，并用等尺度、异尺度和伪条件对照区分机制。",
        "preconditions": [
          "条件在预测时可观测，且不能泄露待预测标签。",
          "需要消除的条件差异确实是干扰尺度，而非研究目标信号。",
          "正常数据足以估计正尺度；共同分布形状等模型条件需核查。"
        ],
        "failure_modes": [
          "若尺度上升本身就是待检测故障，标准化可能削弱真正异常。",
          "若条件间尾部形状不同，除以标准差仍不足以使误报率可比。"
        ],
        "transformation": {
          "before": "直接比较混合设备的原始残差大小。",
          "operation": "分离条件相关的正常尺度，尝试表达相对于该尺度的残差。",
          "after": "提出条件标准化能否改善正常误报率可比性的问题，而不自动声称召回率会提高。"
        },
        "invariants": [
          "保持研究目标为正常误报率可比性，不把它偷换为所有异常召回率提升。",
          "条件估计不读取待评估样本的未来标签。"
        ],
        "evidence_status": "source_inferred",
        "transfer_status": "unvalidated",
        "test_plan": "先检查正常尺度是否属于干扰和尺度族条件，再用相同数据划分、拟合预算的等尺度/异尺度及伪条件对照比较条件误报率与召回率，并报告不确定性；本计划未执行。",
        "source_scope": "仅从这一份虚构材料归纳，不是跨论文确认的通则。",
        "target_transfer": {
          "idea_id": "exercise-only-target-idea",
          "pattern_id": "exercise-pattern-conditional-comparability",
          "pattern_version": "fictional-v2",
          "target": "虚构迁移任务：比较不同采样频率下的设备残差报警。",
          "mapping": [
            {
              "source": "设备条件 c",
              "target": "预测时已知的采样频率条件",
              "status": "待核实：频率是否只改变干扰尺度"
            },
            {
              "source": "正常残差尺度 sigma(c)",
              "target": "正常训练数据中按采样频率估计的尺度",
              "status": "拟议估计方法，尚无运行"
            }
          ],
          "preserved_invariants": [
            "不使用测试标签估计尺度",
            "保持报警目标及数据划分一致"
          ],
          "new_assumptions": [
            "采样频率不改变故障信号的可识别性",
            "频率条件间差异可由正尺度近似而非形状变化解释"
          ],
          "competing_explanation": "观察到的差异来自故障信号丢失或频率相关混叠，而不是正常尺度。",
          "discriminating_prediction": "仅在正尺度模型成立时，正确条件化应比伪条件对照更稳定地改善条件误报率可比性；召回率变化须另测。",
          "falsification": "若匹配预算后正确条件无优势、尺度族假设失效或正常化删掉故障信号，则该目标迁移不受支持或需要收窄。",
          "evidence_status": "计划与系统推断；未执行目标实验"
        }
      }
    ],
    "paper_understanding": {
      "paper_type": "虚构的概念方法说明；不是已发表论文",
      "sources": [
        {
          "source_id": "exercise-source",
          "kind": "full_text",
          "version": "fictional-fixture-v2",
          "status": "read",
          "required": true,
          "path": "EXERCISE_ONLY/not-a-real-paper.md",
          "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
          "exercise_only": true,
          "path_and_hash_status": "模拟输入；该文件不存在，全零值不是任何实际文件的摘要"
        }
      ],
      "coverage": {
        "status": "complete",
        "read_anchor_ids": [
          "s1",
          "s2",
          "s3",
          "s4",
          "s5"
        ],
        "unread_anchor_ids": [],
        "scope": "仅模拟本文件 S1-S5 的阅读覆盖；不代表真实研究阅读"
      },
      "navigation": [
        {
          "anchor_id": "s1",
          "source_id": "exercise-source",
          "kind": "section",
          "locator": "skills/references/idea-trace-example.md#s1",
          "summary": "虚构问题：不同设备的正常残差尺度不可直接比较。"
        },
        {
          "anchor_id": "s2",
          "source_id": "exercise-source",
          "kind": "section",
          "locator": "skills/references/idea-trace-example.md#s2",
          "summary": "虚构作者明确质疑统一原始阈值隐含的尺度可比性。"
        },
        {
          "anchor_id": "s3",
          "source_id": "exercise-source",
          "kind": "section",
          "locator": "skills/references/idea-trace-example.md#s3",
          "summary": "虚构假设、条件标准化公式及共同形状尺度族前提。"
        },
        {
          "anchor_id": "s4",
          "source_id": "exercise-source",
          "kind": "section",
          "locator": "skills/references/idea-trace-example.md#s4",
          "summary": "仅有比较计划，没有实验结果。"
        },
        {
          "anchor_id": "s5",
          "source_id": "exercise-source",
          "kind": "section",
          "locator": "skills/references/idea-trace-example.md#s5",
          "summary": "材料未提供代码、运行记录或研究历史。"
        }
      ],
      "analysis": {
        "problem": {
          "status": "analyzed",
          "summary": "研究张力是原始残差相同却未必有同样的正常罕见程度，目标为条件间误报率可比。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s1"
            },
            {
              "source_id": "exercise-source",
              "anchor_id": "s2"
            }
          ]
        },
        "method": {
          "status": "analyzed",
          "summary": "拟使用 z=|r|/sigma(c)，尺度仅由正常训练数据估计；材料没有证明其效果。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s3"
            }
          ]
        },
        "formalism": {
          "status": "analyzed",
          "summary": "系统将共同形状尺度族表述为 r|c=sigma(c)U，U 分布不依赖 c；这是对 S3 的显式重建，不是原文额外给出的证明。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s3"
            }
          ]
        },
        "figures_tables": {
          "status": "not_applicable",
          "summary": "虚构练习没有图表。",
          "source_refs": [],
          "reason": "S1-S5 只是教学文字；没有图表可分析。"
        },
        "evidence": {
          "status": "unknown",
          "summary": "S4 仅有比较计划，无法判断实际误报率、召回率及机制效果。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s4"
            },
            {
              "source_id": "exercise-source",
              "anchor_id": "s5"
            }
          ],
          "reason": "未提供任何运行或测量结果，不能把计划作为支持结果。"
        },
        "assumptions": {
          "status": "analyzed",
          "summary": "条件可观测、正尺度、共同分布形状且尺度估计来自正常训练数据；迁移还需检查尺度是否为干扰。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s2"
            },
            {
              "source_id": "exercise-source",
              "anchor_id": "s3"
            }
          ]
        },
        "limitations": {
          "status": "analyzed",
          "summary": "没有代码、实验或历史记录；异常召回收益不在已建立证据之内。",
          "source_refs": [
            {
              "source_id": "exercise-source",
              "anchor_id": "s3"
            },
            {
              "source_id": "exercise-source",
              "anchor_id": "s4"
            },
            {
              "source_id": "exercise-source",
              "anchor_id": "s5"
            }
          ]
        }
      },
      "limitations": [
        "全部来源为虚构夹具；path 和 sha256 是显式模拟值，不能用于真实来源核验。",
        "只有计划，无已验证效果；真实作者研究历史不适用。"
      ]
    }
  },
  "idea_trace": [
    {
      "step": 1,
      "trace_id": "t1",
      "statement": "作者在虚构问题设定中指出：同样大小的残差在不同正常噪声尺度下含义不同，研究目标是误报率可比性。",
      "basis": "author_stated",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s1",
          "anchor_id": "s1"
        }
      ],
      "function": "problem_and_observation",
      "evidence_status": "问题设定中的观察；不是实际运行结果",
      "depends_on": [],
      "reasoning_operation": "定位目标与观测尺度之间的张力。",
      "assumptions": [
        "目标是条件间正常误报率可比性。"
      ],
      "alternatives": [],
      "testable_implication": "比较相同原始残差在不同正常条件中的分位位置；此处仅提出检查。"
    },
    {
      "trace_id": "t9",
      "statement": "系统把统一原始残差阈值识别为材料讨论的概念基线瓶颈；材料没有提供实际先例论文或实测失败，不能据此声称整个领域已被证明受限。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "anchor_id": "s1"
        },
        {
          "source_id": "exercise-source",
          "anchor_id": "s2"
        }
      ],
      "depends_on": [
        "t1"
      ],
      "reasoning_operation": "将宽泛的问题缩到一个具体基线机制的前提。",
      "assumptions": [
        "关注的基线确实使用统一原始阈值。"
      ],
      "alternatives": [
        "条件校准或其他基线可能已解决问题，尚未检索。"
      ],
      "testable_implication": "需核对真实最近邻是否具有此瓶颈；本虚构材料不能支持新颖性结论。",
      "function": "prior_work_bottleneck",
      "step": 2
    },
    {
      "step": 3,
      "trace_id": "t2",
      "statement": "作者明确质疑统一原始残差阈值所依赖的正常尺度可比性前提。",
      "basis": "author_stated",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s2",
          "anchor_id": "s2"
        }
      ],
      "function": "challenged_assumption",
      "depends_on": [
        "t9"
      ],
      "reasoning_operation": "识别统一阈值隐含的可比性前提。",
      "assumptions": [
        "统一原始残差阈值被用于控制不同条件的误报率。"
      ],
      "alternatives": [
        "条件分布差异可能来自形状或均值，而不只是尺度。"
      ],
      "testable_implication": "若正常分布已经可比，则本瓶颈未必存在。"
    },
    {
      "step": 4,
      "trace_id": "t3",
      "statement": "系统把从原始残差到条件标准化残差的联系归纳为换表示操作；这是可复用策略的重建，不是作者心理过程的记录。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s2",
          "anchor_id": "s2"
        },
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s3",
          "anchor_id": "s3"
        }
      ],
      "function": "reasoning_operation",
      "depends_on": [
        "t2"
      ],
      "reasoning_operation": "换表示：从绝对残差转为相对于条件正常尺度的残差。",
      "assumptions": [
        "被除去的尺度差异是干扰，不是目标信号。"
      ],
      "alternatives": [
        "直接估计条件分位数也可能控制误报率；本材料未比较。"
      ],
      "testable_implication": "需要比较表示改变是否改善条件可比性，而非只比较总体平均值。"
    },
    {
      "step": 5,
      "trace_id": "t4",
      "statement": "作者提出：在共同形状的正尺度族假设下，仅用正常训练数据估计尺度的标准化可能改善正常误报率可比性；不承诺异常召回率提高。",
      "basis": "author_stated",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s3",
          "anchor_id": "s3"
        }
      ],
      "function": "new_hypothesis",
      "depends_on": [
        "t2"
      ],
      "validation_status": "proposed_not_tested",
      "reasoning_operation": "从尺度假设提出条件标准化机制。",
      "assumptions": [
        "条件可观测。",
        "正常分布属于共同形状的正尺度族。"
      ],
      "alternatives": [
        "额外拟合自由度也可能造成表面改善。"
      ],
      "testable_implication": "假设成立且尺度估计充分准确时，条件标准化后的正常分布应更可比。"
    },
    {
      "trace_id": "t10",
      "statement": "系统将 S3 的共同形状尺度族写为 r|c=sigma(c)U，U 的分布不随 c 变化；由此 z=|U| 才得到条件分布相同的理想化预测。这是形式化重建，未考虑有限样本估计误差。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "anchor_id": "s3"
        }
      ],
      "depends_on": [
        "t4"
      ],
      "reasoning_operation": "把机制条件显式写成可检验的分布模型并推出预测。",
      "assumptions": [
        "sigma(c)>0。",
        "U 的分布不依赖 c。",
        "理想推导使用真实尺度，实际估计误差需另分析。"
      ],
      "alternatives": [
        "条件间存在位置变化、尾部形状变化或不同异常机制。"
      ],
      "testable_implication": "检查标准化后正常分布是否仍具有系统性条件差异；若有，理想尺度模型不足。",
      "function": "formalization",
      "step": 6
    },
    {
      "step": 7,
      "trace_id": "t5",
      "statement": "系统补充一个竞争解释：未来若出现改善，可能来自额外拟合自由度，而不是正确识别了条件尺度。虚构材料没有提出或检验这个解释。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s3",
          "anchor_id": "s3"
        },
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s4",
          "anchor_id": "s4"
        }
      ],
      "function": "competing_explanation_and_counterfactual",
      "depends_on": [
        "t4"
      ],
      "competing_explanations": [
        "有意义的条件尺度校正",
        "额外拟合自由度或调参预算导致表面改善"
      ],
      "counterfactual": "在样本量、参数量和调参预算可比时，加入与正常尺度无关的伪条件对照，检查它能否获得同样改善。",
      "validation_status": "system_proposed_control_not_run",
      "reasoning_operation": "构造预算匹配的反事实对照以区分条件信息与额外自由度。",
      "assumptions": [
        "拟合预算、参数量、样本划分需可比。"
      ],
      "alternatives": [
        "伪条件拟合",
        "正确尺度机制"
      ],
      "testable_implication": "若无关伪条件也有同样改善，不能把改善归因于正确条件尺度。"
    },
    {
      "step": 8,
      "trace_id": "t6",
      "statement": "系统据尺度假设推导判别预测：在其余分布条件可比时，正确条件化的价值应随真实尺度差异增大而更明显；等尺度条件下不应期待稳定的尺度校正优势。实际结果未知。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s3",
          "anchor_id": "s3"
        },
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s4",
          "anchor_id": "s4"
        }
      ],
      "function": "discriminating_prediction",
      "depends_on": [
        "t10",
        "t5"
      ],
      "predictions": [
        {
          "condition": "正尺度、共同形状、具有足够估计精度的异尺度条件",
          "expected_observation": "正确条件化应改善条件间正常误报率可比性，并与伪条件对照表现不同"
        },
        {
          "condition": "同样的分布形状且尺度相等",
          "expected_observation": "不预期存在稳定的尺度校正优势；需区分有限样本波动"
        }
      ],
      "validation_status": "predictions_not_observations",
      "reasoning_operation": "比较等尺度与异尺度边界下的区分预测。",
      "assumptions": [
        "分布形状与其余条件可比。",
        "估计误差足够小，或已量化其不确定性。"
      ],
      "alternatives": [
        "有限样本波动",
        "模型条件失配"
      ],
      "testable_implication": "等尺度下不预期稳定的尺度校正优势；异尺度下需对比正确条件与伪条件。"
    },
    {
      "trace_id": "t11",
      "statement": "S4 只记录实验计划，S5 未提供执行材料。系统因此只确认假设与计划存在，无法判断效果、因果解释或复现情况；这不是一个负面实验结果。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "anchor_id": "s4"
        },
        {
          "source_id": "exercise-source",
          "anchor_id": "s5"
        }
      ],
      "depends_on": [
        "t4",
        "t6"
      ],
      "reasoning_operation": "限制证据能支持的结论，区分计划与实际结果。",
      "assumptions": [],
      "alternatives": [
        "方法可能有效、无效或只在部分条件有效，目前均未区分。"
      ],
      "testable_implication": "需要真实执行、原始输出和预先预测比较才能更新效果判断。",
      "function": "evidence_strength",
      "step": 9
    },
    {
      "step": 10,
      "trace_id": "t7",
      "statement": "系统认为迁移时必须先证明条件尺度属于可消除的干扰：若尺度变化本身就是故障信号，直接沿用标准化可能损害目标。此迁移边界尚未经实证。",
      "basis": "reconstructed",
      "source_refs": [
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s2",
          "anchor_id": "s2"
        },
        {
          "source_id": "exercise-source",
          "locator": "skills/references/idea-trace-example.md#s3",
          "anchor_id": "s3"
        }
      ],
      "function": "transfer_conditions",
      "depends_on": [
        "t3",
        "t4"
      ],
      "transfer_conditions": [
        "条件在预测时可观测",
        "训练正常尺度对目标环境仍有意义",
        "标准化不删除目标异常信号"
      ],
      "counterexamples": [
        "设备噪声方差上升本身就是需要识别的故障"
      ],
      "reasoning_operation": "检查被移除变量是否同时携带目标信号。",
      "assumptions": [
        "干扰与目标信号可以在当前设置下区分。"
      ],
      "alternatives": [
        "尺度变化本身是故障。"
      ],
      "testable_implication": "若正常化削弱真实故障报警，迁移需要拒绝或收窄。"
    },
    {
      "step": 11,
      "trace_id": "t8",
      "statement": "材料没有披露作者何时、为何首次想到该表示，也没有失败尝试顺序；真实研究历史未知。前七步不能据此转写为作者经历的时间线。",
      "basis": "unknown",
      "source_refs": [],
      "function": "unknown_history",
      "depends_on": [],
      "reasoning_operation": "未知：材料未披露灵感形成与尝试顺序。",
      "assumptions": [],
      "alternatives": [],
      "testable_implication": "不适用于效果实验；只有真实研究日志或作者明确记录才可能核对历史，本练习没有这些材料。"
    }
  ],
  "code_tools": [],
  "limitations": [
    "全部材料为虚构练习，不能作为真实科学证据或专家能力证明。",
    "source.path 为不存在的模拟路径，sha256 为全零模拟值；只供结构测试，不能通过真实来源/文件核验或提交研究运行。",
    "没有源码、工具调用、实验日志、实际指标或复现记录。",
    "推理策略与迁移条件由系统从虚构文字归纳，未经实际研究验证。"
  ]
}
```

## 图与策略的对应

问题张力 `t1` → 概念基线瓶颈 `t9` → 被挑战前提 `t2`。前提分别支持系统归纳的换表示 `t3` 与作者提出的机制 `t4`；机制再支撑形式化 `t10` 与竞争解释 `t5`，两支汇入判别预测 `t6`。`t11` 限制当前证据能支持的结论，`t7` 检查迁移失败边界。`t8` 保留未知历史，没有伪造与其他节点之间的时间边。

策略索引回链到多个具体节点，另用 `target_transfer` 展示面向一个虚构 idea 的对应关系、新前提与反证标准。它是计划，不是结果；`evidence_status: source_inferred` 与 `transfer_status: unvalidated` 分别表示系统归纳和未验证迁移。

## 如何检查这个练习

- 用 `validate_artifact("paper", data)` 检查整份 JSON；覆盖分区、来源/锚点、图的无环依赖与策略引用同时校验。
- `t1/t2/t4` 只转述虚构作者明确的论证；系统新增的瓶颈归纳、换表示、形式化、对照和边界保持 `reconstructed`。
- `paper_understanding.analysis.evidence` 是 `unknown`；图表为 `not_applicable` 并给理由。不能把已读模拟材料当作方法有效的证据。
- `reasoning_patterns` 包含前提、失败模式、不变量和目标检验；单来源归纳不能声称普遍有效。原模型分析与目标迁移的新增假设分开。
- 空 `code_tools` 与非空 `limitations` 如实表示没有可调用实现。没有运行日志、真实文件摘要、可导出工具或 `_asset`。
- 结构通过只服务于这个虚构夹具；真实研究必须提供实际文件、摘要和阅读证据，不能复制模拟值。
