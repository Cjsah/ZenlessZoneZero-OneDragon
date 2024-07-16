from one_dragon.base.config.yaml_config import YamlConfig


class ProjectConfig(YamlConfig):

    def __init__(self):
        super().__init__(module_name='project')

        self.project_name = self.get('project_name')
        self.win_title = self.get('win_title')
        self.python_version = self.get('python_version')
        self.github_repository = self.get('github_repository')
        self.gitee_repository = self.get('gitee_repository')
        self.project_git_branch = self.get('project_git_branch')
        self.requirements = self.get('requirements')

        self.screen_standard_width = int(self.get('screen_standard_width'))
        self.screen_standard_height = int(self.get('screen_standard_height'))
