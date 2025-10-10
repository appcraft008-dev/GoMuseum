/// GoMuseum 设置页面
library;

import 'package:flutter/material.dart';
import 'package:gomuseum_app/theme/dimensions.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
      ),
      body: ListView(
        children: [
          // 账户部分
          _buildSection(
            context,
            title: '账户',
            children: [
              ListTile(
                leading: const CircleAvatar(
                  child: Icon(Icons.person),
                ),
                title: const Text('登录/注册'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {},
              ),
            ],
          ),
          
          const Divider(),
          
          // 通用设置
          _buildSection(
            context,
            title: '通用',
            children: [
              ListTile(
                leading: const Icon(Icons.language),
                title: const Text('语言'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '中文',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const Icon(Icons.chevron_right),
                  ],
                ),
                onTap: () {},
              ),
              SwitchListTile(
                secondary: const Icon(Icons.dark_mode),
                title: const Text('暗色模式'),
                value: false,
                onChanged: (value) {},
              ),
              ListTile(
                leading: const Icon(Icons.delete_outline),
                title: const Text('清除缓存'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {},
              ),
            ],
          ),
          
          const Divider(),
          
          // 关于
          _buildSection(
            context,
            title: '关于',
            children: [
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('版本号'),
                trailing: Text(
                  'v1.0.0',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ),
              ListTile(
                leading: const Icon(Icons.article_outlined),
                title: const Text('许可证'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {},
              ),
              ListTile(
                leading: const Icon(Icons.help_outline),
                title: const Text('关于我们'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {},
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSection(
    BuildContext context, {
    required String title,
    required List<Widget> children,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.fromLTRB(
            AppDimensions.spacing16,
            AppDimensions.spacing16,
            AppDimensions.spacing16,
            AppDimensions.spacing8,
          ),
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
        ),
        ...children,
      ],
    );
  }
}
