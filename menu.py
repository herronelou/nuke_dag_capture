import nuke

import dag_capture


def create_nuke_menu():
    nuke_menu = nuke.menu("Nuke")
    nuke_menu.addCommand(
        name="Screenshot",
        command=dag_capture.open_dag_capture,
        tooltip="Open DAG screenshot menu",
    )


if __name__ == '__main__':
    create_nuke_menu()
